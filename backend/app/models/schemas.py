from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def current_utc_time():
    return datetime.now(timezone.utc)


# --- Health Check ---
class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Current service health status")
    app_name: str
    version: str = "1.0.0"
    environment: str
    timestamp: datetime = Field(default_factory=current_utc_time)


# --- Citation & Source Evidence ---
class Citation(BaseModel):
    act_name: Optional[str] = Field(default="Unknown Act", description="Name of the Indian Act or Policy")
    section: Optional[str] = Field(default=None, description="Section, Rule, or Article number")
    document_name: str = Field(..., description="Original filename of the legal source")
    page_number: Optional[int] = Field(default=None, description="Page number in the PDF")
    snippet: str = Field(..., description="Excerpt from the source document used as evidence")
    relevance_score: Optional[float] = Field(default=None, description="Similarity or retrieval relevance score")


# --- Chat Models ---
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="Unique ID of existing conversation")
    question: str = Field(..., min_length=1, description="User question in English, Hindi, or Hinglish")
    provider: Optional[str] = Field(default=None, description="LLM provider override: 'gemini', 'openai', or 'ollama'")


class ChatResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str = Field(..., description="Evidence-grounded answer or unavailability notice")
    direct_answer: Optional[str] = Field(default=None, description="Concise direct answer")
    legal_explanation: Optional[str] = Field(default=None, description="Detailed legal explanation")
    citations: List[Citation] = Field(default_factory=list, description="Preserved legal citations")
    disclaimer: str = Field(
        default="This chatbot provides legal and policy information for educational purposes only. It is not formal legal advice.",
        description="Mandatory legal disclaimer"
    )
    provider_used: Optional[str] = None
    tokens_used: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    created_at: datetime = Field(default_factory=current_utc_time)


# --- Document Models ---
class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    file_size_bytes: int = 0
    act_name: Optional[str] = None
    total_pages: int = 0
    total_chunks: int = 0
    file_hash: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=current_utc_time)
    status: str = "indexed"  # pending, indexed, failed
    error_message: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentMetadata
    processing_time_seconds: Optional[float] = None


class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    act_name: str
    status: str
    total_pages: int
    total_chunks: int
    file_hash: str
    uploaded_at: Optional[str] = None


# --- Retrieval Models (Stage 3) ---
class RetrievalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Legal question or keywords")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of evidence chunks to return")
    relevance_threshold: Optional[float] = Field(default=0.35, ge=0.0, le=1.0, description="Minimum similarity score")
    act_name_filter: Optional[str] = Field(default=None, description="Optional filter by exact Act name")
    conversation_context: Optional[str] = Field(default=None, description="Recent conversation turns for follow-up disambiguation")


class EvidenceChunkSchema(BaseModel):
    chunk_id: str
    text: str
    act_name: str
    section_number: Optional[str] = None
    page_number: int
    source_file: str
    document_id: str
    similarity_score: float
    semantic_distance: float
    is_exact_section_match: bool = False


class ProcessedQuerySchema(BaseModel):
    raw_query: str
    clean_query: str
    search_query: str
    target_section: Optional[str] = None
    target_act: Optional[str] = None
    detected_keywords: List[str] = Field(default_factory=list)
    is_hindi_hinglish: bool = False
    unsupported_act_detected: Optional[str] = None


class RetrievalSearchResponse(BaseModel):
    query: ProcessedQuerySchema
    evidence_chunks: List[EvidenceChunkSchema]
    is_unsupported_act: bool = False
    unsupported_act_name: Optional[str] = None
    has_sufficient_evidence: bool = False
    total_candidates_examined: int = 0


# --- Conversation History Models ---
class MessageItem(BaseModel):
    id: str
    role: str  # 'user' | 'assistant'
    content: str
    direct_answer: Optional[str] = None
    legal_explanation: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=current_utc_time)


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    conversation_id: str
    title: str
    messages: List[MessageItem]
    created_at: datetime
    updated_at: datetime
