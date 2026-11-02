import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.core.logging_config import logger
from app.ingestion.chunker import DocumentChunk


class VectorStoreError(Exception):
    """Custom exception for vector store operations."""
    pass


class VectorStoreService:
    """
    Manages persistent ChromaDB vector store operations and document registry.
    """

    _instance: Optional["VectorStoreService"] = None

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or settings.VECTOR_STORE_DIR
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self.registry_path = settings.PROCESSED_DIR / "documents_registry.json"

        # Initialize ChromaDB persistent client
        logger.info(f"Connecting to ChromaDB at: {self.persist_dir}")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Indian Legal Documents and Statutory Chunks"}
        )
        self._ensure_registry()

    def _ensure_registry(self):
        """Ensure documents_registry.json exists."""
        if not self.registry_path.exists():
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load document index registry from disk."""
        self._ensure_registry()
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read registry: {e}")
            return {}

    def _save_registry(self, registry: Dict[str, Dict[str, Any]]):
        """Save document index registry to disk."""
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    @classmethod
    def get_instance(cls, persist_dir: Optional[Path] = None) -> "VectorStoreService":
        if cls._instance is None or persist_dir is not None:
            cls._instance = cls(persist_dir)
        return cls._instance

    def get_document_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if a document with the exact same content hash is already indexed."""
        registry = self._load_registry()
        for doc in registry.values():
            if doc.get("file_hash") == file_hash:
                return doc
        return None

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document metadata by document ID."""
        registry = self._load_registry()
        return registry.get(document_id)

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all indexed documents with statistics."""
        registry = self._load_registry()
        return list(registry.values())

    def add_document_chunks(
        self,
        document_id: str,
        filename: str,
        file_hash: str,
        act_name: str,
        total_pages: int,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
        raw_file_path: Optional[str] = None
    ) -> int:
        """
        Add document chunks and embeddings into ChromaDB and update registry.
        Returns the number of successfully indexed chunks.
        """
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                f"Mismatch: Got {len(chunks)} chunks but {len(embeddings)} embeddings."
            )

        if not chunks:
            logger.warning(f"No chunks provided for document {document_id}")
            return 0

        # Prevent duplicate document indexing
        existing = self.get_document_by_hash(file_hash)
        if existing and existing.get("document_id") != document_id:
            raise VectorStoreError(
                f"Duplicate document detected! Already indexed as '{existing['filename']}' "
                f"(ID: {existing['document_id']})."
            )

        chunk_ids = [c.chunk_id for c in chunks]
        documents_text = [c.text for c in chunks]
        metadatas = [c.to_metadata() for c in chunks]

        # Add embedding model info into metadata
        for meta in metadatas:
            meta["embedding_model"] = settings.EMBEDDING_MODEL_NAME

        try:
            logger.info(f"Upserting {len(chunks)} chunks into ChromaDB for '{act_name}'...")
            self.collection.upsert(
                ids=chunk_ids,
                documents=documents_text,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            # Verification of stored chunk count
            verification = self.collection.get(where={"document_id": document_id})
            stored_count = len(verification["ids"]) if verification and "ids" in verification else 0

            if stored_count != len(chunks):
                logger.warning(
                    f"Chunk count verification mismatch: expected {len(chunks)}, got {stored_count}"
                )

            # Update document registry
            registry = self._load_registry()
            registry[document_id] = {
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "act_name": act_name,
                "total_pages": total_pages,
                "total_chunks": stored_count,
                "raw_file_path": raw_file_path or "",
                "status": "indexed",
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_registry(registry)

            logger.info(
                f"Successfully indexed document '{filename}' with {stored_count} chunks in ChromaDB."
            )
            return stored_count

        except Exception as e:
            logger.error(f"Failed to index chunks in ChromaDB: {e}")
            raise VectorStoreError(f"Vector storage error: {str(e)}")

    def delete_document(
        self,
        document_id: str,
        delete_raw_file: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a document's indexed chunks from ChromaDB and registry.
        Preserves original raw PDF file unless delete_raw_file=True.
        """
        registry = self._load_registry()
        if document_id not in registry:
            raise VectorStoreError(f"Document ID '{document_id}' not found in registry.")

        doc_info = registry[document_id]

        try:
            # 1. Delete all chunks matching document_id from ChromaDB
            self.collection.delete(where={"document_id": document_id})
            logger.info(f"Deleted ChromaDB vectors for document: {document_id}")

            # 2. Optionally delete raw file
            raw_path = doc_info.get("raw_file_path")
            if delete_raw_file and raw_path and Path(raw_path).exists():
                try:
                    Path(raw_path).unlink()
                    logger.info(f"Deleted raw PDF file: {raw_path}")
                except Exception as e:
                    logger.warning(f"Could not delete raw file '{raw_path}': {e}")

            # 3. Clean processed folder
            processed_folder = settings.PROCESSED_DIR / document_id
            if processed_folder.exists() and processed_folder.is_dir():
                import shutil
                shutil.rmtree(processed_folder, ignore_errors=True)

            # 4. Remove from registry
            del registry[document_id]
            self._save_registry(registry)

            return {
                "document_id": document_id,
                "filename": doc_info.get("filename"),
                "deleted": True,
                "raw_file_preserved": not delete_raw_file,
            }

        except Exception as e:
            logger.error(f"Failed to delete document '{document_id}': {e}")
            raise VectorStoreError(f"Deletion failed: {str(e)}")

    def count_chunks(self, document_id: Optional[str] = None) -> int:
        """Count total chunks or chunks for a specific document."""
        if document_id:
            res = self.collection.get(where={"document_id": document_id})
            return len(res["ids"]) if res and "ids" in res else 0
        return self.collection.count()
