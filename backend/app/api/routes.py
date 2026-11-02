from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, status
from typing import List, Optional
from datetime import datetime, timezone

from app.config import settings
from app.models.schemas import (
    HealthResponse,
    ChatRequest,
    ChatResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    DocumentStatusResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    EvidenceChunkSchema,
    ProcessedQuerySchema,
    ConversationSummary,
    ConversationDetail,
)
from app.core.logging_config import logger
from app.ingestion.validator import PDFValidationError
from app.database.vector_store import VectorStoreService, VectorStoreError
from app.services.ingestion_service import DocumentIngestionService
from app.retrieval.retriever import LegalRetriever
from app.services.chat_service import ChatService
from app.database.conversation_store import get_conversation_store

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version="1.0.0",
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
    )


# --- Document Ingestion Endpoints (Stage 2) ---

@router.post(
    "/api/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"]
)
async def upload_document(
    file: UploadFile = File(..., description="Indian Legal PDF file to ingest and index"),
    act_name: Optional[str] = Form(None, description="Optional Act/Policy name override")
):
    """
    Upload and index a legal PDF document.
    Validates PDF integrity, cleans text, performs section-aware chunking,
    generates dense embeddings, and persists chunks into ChromaDB.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported. Please provide a file with a .pdf extension."
        )

    try:
        content = await file.read()
        ingestion_service = DocumentIngestionService()
        result = ingestion_service.process_and_index_pdf(
            file_bytes=content,
            filename=file.filename,
            act_name=act_name
        )

        doc_meta = DocumentMetadata(
            document_id=result["document_id"],
            filename=result["filename"],
            file_size_bytes=result["file_size_bytes"],
            act_name=result["act_name"],
            total_pages=result["total_pages"],
            total_chunks=result["total_chunks"],
            file_hash=result["file_hash"],
            status="indexed",
        )

        return DocumentUploadResponse(
            message=f"Document '{result['act_name']}' successfully indexed with {result['total_chunks']} statutory chunks.",
            document=doc_meta,
            processing_time_seconds=result.get("processing_time_seconds")
        )

    except PDFValidationError as e:
        logger.warning(f"Validation error during upload of '{file.filename}': {e}")
        # If duplicate document error, return HTTP 409 Conflict
        if "already indexed" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except VectorStoreError as e:
        logger.error(f"Vector store error during upload of '{file.filename}': {e}")
        if "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error during document upload '{file.filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing the document: {str(e)}"
        )


@router.get("/api/documents", response_model=List[DocumentMetadata], tags=["Documents"])
async def list_documents():
    """List all indexed legal documents with chunk counts and metadata."""
    try:
        vector_store = VectorStoreService.get_instance()
        docs = vector_store.list_documents()
        return [
            DocumentMetadata(
                document_id=d["document_id"],
                filename=d["filename"],
                file_size_bytes=d.get("file_size_bytes", 0),
                act_name=d.get("act_name", "Indian Legal Act"),
                total_pages=d.get("total_pages", 0),
                total_chunks=d.get("total_chunks", 0),
                file_hash=d.get("file_hash"),
                status=d.get("status", "indexed"),
            )
            for d in docs
        ]
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/api/documents/{document_id}", response_model=DocumentMetadata, tags=["Documents"])
async def get_document(document_id: str):
    """Retrieve indexed document metadata by ID."""
    vector_store = VectorStoreService.get_instance()
    doc = vector_store.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found."
        )

    return DocumentMetadata(
        document_id=doc["document_id"],
        filename=doc["filename"],
        file_size_bytes=doc.get("file_size_bytes", 0),
        act_name=doc.get("act_name", "Indian Legal Act"),
        total_pages=doc.get("total_pages", 0),
        total_chunks=doc.get("total_chunks", 0),
        file_hash=doc.get("file_hash"),
        status=doc.get("status", "indexed"),
    )


@router.get("/api/documents/{document_id}/status", response_model=DocumentStatusResponse, tags=["Documents"])
async def get_document_status(document_id: str):
    """Retrieve indexing and ingestion status of a specific document."""
    vector_store = VectorStoreService.get_instance()
    doc = vector_store.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' was not found in the index."
        )

    return DocumentStatusResponse(
        document_id=doc["document_id"],
        filename=doc["filename"],
        act_name=doc.get("act_name", "Indian Legal Act"),
        status=doc.get("status", "indexed"),
        total_pages=doc.get("total_pages", 0),
        total_chunks=doc.get("total_chunks", 0),
        file_hash=doc.get("file_hash", ""),
        uploaded_at=doc.get("indexed_at"),
    )


@router.delete("/api/documents/{document_id}", tags=["Documents"])
async def delete_document(
    document_id: str,
    delete_raw_file: bool = Query(
        False,
        description="Whether to also permanently delete the uploaded raw PDF file from storage"
    )
):
    """
    Delete an indexed legal document from the vector store.
    By default, preserves the original uploaded PDF for legal compliance.
    """
    vector_store = VectorStoreService.get_instance()
    try:
        result = vector_store.delete_document(document_id, delete_raw_file=delete_raw_file)
        return {
            "message": f"Document '{document_id}' successfully removed from vector index.",
            "details": result,
        }
    except VectorStoreError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# --- RAG Semantic Retrieval Endpoint (Stage 3) ---

@router.post(
    "/api/retrieval/search",
    response_model=RetrievalSearchResponse,
    tags=["Retrieval"]
)
async def retrieval_search(request: RetrievalSearchRequest):
    """
    Execute semantic and hybrid legal search across indexed statutory documents.
    Supports English, Hindi, Hinglish queries, exact section targeting,
    metadata filtering, relevance thresholds, and unsupported Act detection.
    """
    try:
        retriever = LegalRetriever()
        result = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            relevance_threshold=request.relevance_threshold,
            act_name_filter=request.act_name_filter,
            conversation_context=request.conversation_context,
        )

        processed_query_schema = ProcessedQuerySchema(
            raw_query=result.processed_query.raw_query,
            clean_query=result.processed_query.clean_query,
            search_query=result.processed_query.search_query,
            target_section=result.processed_query.target_section,
            target_act=result.processed_query.target_act,
            detected_keywords=result.processed_query.detected_keywords,
            is_hindi_hinglish=result.processed_query.is_hindi_hinglish,
            unsupported_act_detected=result.processed_query.unsupported_act_detected,
        )

        evidence_chunk_schemas = [
            EvidenceChunkSchema(
                chunk_id=c.chunk_id,
                text=c.text,
                act_name=c.act_name,
                section_number=c.section_number,
                page_number=c.page_number,
                source_file=c.source_file,
                document_id=c.document_id,
                similarity_score=c.similarity_score,
                semantic_distance=c.semantic_distance,
                is_exact_section_match=c.is_exact_section_match,
            )
            for c in result.chunks
        ]

        return RetrievalSearchResponse(
            query=processed_query_schema,
            evidence_chunks=evidence_chunk_schemas,
            is_unsupported_act=result.is_unsupported_act,
            unsupported_act_name=result.unsupported_act_name,
            has_sufficient_evidence=result.has_sufficient_evidence,
            total_candidates_examined=result.total_candidates_examined,
        )
    except Exception as e:
        logger.error(f"Error during retrieval search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval search failed: {str(e)}"
        )


# --- RAG Legal Chat & Conversation Endpoints (Stage 4) ---

@router.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """
    RAG-powered conversational assistant for Indian legal queries.
    Retrieves statutory chunks from ChromaDB, grounds response in retrieved provisions,
    verifies citations, admits absence for unindexed Acts, and retains conversation history.
    """
    try:
        service = ChatService()
        response = await service.process_chat(request)
        return response
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


@router.get("/api/conversations", response_model=List[ConversationSummary], tags=["Conversations"])
async def list_conversations():
    """List all previous conversation histories."""
    store = get_conversation_store()
    return store.list_conversations()


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail, tags=["Conversations"])
async def get_conversation(conversation_id: str):
    """Get full conversation details and message history by session ID."""
    store = get_conversation_store()
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    return conv


@router.delete("/api/conversations/{conversation_id}", tags=["Conversations"])
async def delete_conversation(conversation_id: str):
    """Delete a conversation session."""
    store = get_conversation_store()
    deleted = store.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    return {"message": f"Conversation '{conversation_id}' successfully deleted."}
