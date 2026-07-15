from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BuildPolicyChunksRequest(BaseModel):
    policy_id: Optional[UUID] = Field(default=None, description="특정 정책만 재임베딩할 때 사용")
    limit: Optional[int] = Field(default=None, ge=1, le=5000, description="처리할 policy_documents 수 제한")
    force: bool = Field(default=False, description="기존 청크가 있어도 삭제 후 전체 재생성할지 여부")
    chunk_size: Optional[int] = Field(default=None, ge=100, le=1000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=300)


class BuildPolicyChunksResponse(BaseModel):
    embedding_models: Dict[str, str]
    chunk_size: int
    chunk_overlap: int
    force: bool
    schema: Dict[str, Any] | None = None
    target_documents: int
    embedded_documents: int
    skipped_documents: int = 0
    metadata_backfilled: int = 0
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


class ChatPolicyCandidate(BaseModel):
    """메인 채팅에서 사용자가 선택할 수 있는 공고 후보."""

    policy_id: str
    title: str
    summary: Optional[str] = None
    support_type: Optional[str] = None
    apply_end: Optional[str] = None
    score: float
    source_count: int


class ChatSearchResponse(BaseModel):
    query: str
    expanded_query: str
    intent_tags: List[str]
    response_mode: Literal["answer", "policy_selection", "out_of_scope", "no_result"] = "answer"
    candidates: List[ChatPolicyCandidate] = []
    sources: List[ChatChunkSource]


class ChatAnswerRequest(ChatSearchRequest):
    session_id: Optional[UUID] = Field(
        default=None,
        description="로그인 사용자의 대화 세션 ID. 없으면 새 세션을 만든다.",
    )
    selected_policy_id: Optional[UUID] = Field(
        default=None,
        description="프론트가 로컬에 들고 있는 선택 공고 ID. 서버 세션 문맥 복구용으로 사용한다.",
    )


class ChatAnswerResponse(ChatSearchResponse):
    answer: str
    session_id: UUID
    context_policy_id: Optional[str] = None
    active_policy_id: Optional[str] = None
    langsmith_enabled: bool
    langsmith_project: Optional[str] = None


class SelectChatPolicyRequest(BaseModel):
    policy_id: UUID


class ChatSessionResponse(BaseModel):
    session_id: UUID
    active_policy_id: Optional[str] = None


class PolicyChunkStatsResponse(BaseModel):
    policy_documents: int
    policy_chunks: int
    embedded_chunks: int
    failed_chunks: int
    chunked_documents: int
