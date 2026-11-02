import time
from pathlib import Path
from typing import Dict, Any, Optional

from app.ingestion.validator import PDFValidator, PDFValidationError
from app.ingestion.extractor import PDFExtractor
from app.ingestion.chunker import LegalChunker
from app.services.embedding_service import EmbeddingService
from app.database.vector_store import VectorStoreService, VectorStoreError
from app.core.logging_config import logger


class DocumentIngestionService:
    """
    Coordinates the complete PDF document ingestion workflow:
    Validation -> Raw Storage -> Extraction -> Cleaning -> Chunking -> Embedding -> Vector DB Indexing.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        vector_store: Optional[VectorStoreService] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.chunker = LegalChunker(target_chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store = vector_store or VectorStoreService.get_instance()
        self.embedding_service = embedding_service or EmbeddingService.get_instance()

    def process_and_index_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        act_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute full document ingestion pipeline for an uploaded PDF.
        """
        start_time = time.time()
        logger.info(f"Beginning ingestion pipeline for: {filename}")

        # Step 1: Pre-validation and Duplicate Detection via File Hash
        file_hash = PDFValidator.calculate_file_hash(file_bytes)
        existing_doc = self.vector_store.get_document_by_hash(file_hash)
        if existing_doc:
            raise PDFValidationError(
                f"Document is already indexed as '{existing_doc['filename']}' "
                f"(Act: '{existing_doc['act_name']}', ID: '{existing_doc['document_id']}'). "
                f"Duplicate indexing prevented."
            )

        # Step 2: Validate and safely store raw PDF file
        document_id, raw_path, _ = PDFValidator.save_raw_document(file_bytes, filename)

        try:
            # Step 3: Extract text, page numbers, metadata, and sections using PyMuPDF
            extracted_doc = PDFExtractor.extract_document(
                file_path=raw_path,
                document_id=document_id,
                act_name_override=act_name
            )

            # Step 4: Chunk document while preserving statutory provisions and section metadata
            chunks = self.chunker.chunk_document(extracted_doc)
            if not chunks:
                raise PDFValidationError(
                    "No meaningful text could be extracted from this PDF. "
                    "Ensure the document is a readable, text-based PDF."
                )

            # Step 5: Generate dense vector embeddings for all chunks
            chunk_texts = [c.text for c in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_texts)

            # Step 6: Store chunks, metadata, and embeddings in ChromaDB
            stored_count = self.vector_store.add_document_chunks(
                document_id=document_id,
                filename=filename,
                file_hash=file_hash,
                act_name=extracted_doc.act_name,
                total_pages=extracted_doc.total_pages,
                chunks=chunks,
                embeddings=embeddings,
                raw_file_path=str(raw_path)
            )

            elapsed = time.time() - start_time
            logger.info(
                f"Successfully ingested '{filename}' (ID: {document_id}) "
                f"in {elapsed:.2f}s: {extracted_doc.total_pages} pages, {stored_count} chunks indexed."
            )

            return {
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "act_name": extracted_doc.act_name,
                "total_pages": extracted_doc.total_pages,
                "total_chunks": stored_count,
                "file_size_bytes": len(file_bytes),
                "status": "indexed",
                "processing_time_seconds": round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"Ingestion pipeline failed for '{filename}': {e}")
            # Clean up the raw file if extraction/indexing failed
            if raw_path.exists():
                try:
                    raw_path.unlink()
                except Exception:
                    pass
            raise
