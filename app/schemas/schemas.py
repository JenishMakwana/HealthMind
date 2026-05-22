from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ─── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Conversations ─────────────────────────────────────────────────────────────

class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = "New Chat"


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# ─── Messages ──────────────────────────────────────────────────────────────────

class SourceChunk(BaseModel):
    doc_id: str
    filename: str
    title: str
    chunk_index: int
    page_number: Optional[int] = None
    text: str
    score: float
    retrieval_method: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: Optional[List[SourceChunk]] = None
    meta: Optional[dict[str, Any]] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── RAG / Query ───────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    conversation_id: str          # must exist in user's chat DB
    top_k: Optional[int] = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    message_id: str
    conversation_id: str
    query: str
    search_query: str
    answer: str
    sources: List[SourceChunk]
    model: str
    retrieval_strategy: str
    conversation_turns_used: int
    retrieval_ms: float
    rerank_ms: float
    generation_ms: float


class SpeechToTextResponse(BaseModel):
    text: str
    language: Optional[str] = None
    model: str
    filename: str




# ─── Documents ─────────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    filename: str
    title: str
    source: Optional[str]
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    uploaded_by: str
    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    document_id: str
    message: str


class BatchIngestResponse(BaseModel):
    document_ids: List[str]
    message: str
    rejected_files: Optional[List[str]] = None


# ─── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    qdrant: str
    llm: str
    version: str

