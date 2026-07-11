from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BuildPolicyChunksRequest(BaseModel):
    policy_id: Optional[UUID] = Field(default=None, description="특정 정책만 재임베딩할 때 사용")
    limit: Optional[int] = Field(default=None, ge=1, le=5000, description="처리할 policy_documents 수 제한")
    force: bool = Field(default=True, description="기존 청크가 있어도 삭제 후 재생성할지 여부")
    provider: Optional[str] = Field(default=None, description="openai | gemini | ollama")
    model_name: Optional[str] = Field(default=None, description="임베딩 모델명")
    chunk_size: Optional[int] = Field(default=None, ge=100, le=1000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=300)


class BuildPolicyChunksResponse(BaseModel):
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    force: bool
    schema: Dict[str, Any] | None = None
    target_documents: int
    embedded_documents: int
    failed_documents: int
    created_chunks: int
    failures: List[Dict[str, Any]] = []


class ChatSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=6, ge=1, le=20)


class ChatChunkSource(BaseModel):
    chunk_id: str
    policy_id: str
    document_id: str
    chunk_index: int
    similarity: float
    rerank_score: Optional[float] = None
    chunk_text: str
    metadata: Dict[str, Any]
    policy_title: Optional[str] = None
    document_type: Optional[str] = None
    document_title: Optional[str] = None
    source_ref: Optional[str] = None
    apply_start: Optional[str] = None
    apply_end: Optional[str] = None
    contact_points: List[str] = []
    question_hints: List[str] = []


class ChatSearchResponse(BaseModel):
    query: str
    expanded_query: str
    intent_tags: List[str]
    sources: List[ChatChunkSource]


class ChatAnswerRequest(ChatSearchRequest):
    pass


class ChatAnswerResponse(ChatSearchResponse):
    answer: str
    langsmith_enabled: bool
    langsmith_project: Optional[str] = None


class PolicyChunkStatsResponse(BaseModel):
    policy_documents: int
    policy_chunks: int
    embedded_chunks: int
    failed_chunks: int
    chunked_documents: int
