from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.normalized_policy import NormalizedPolicy
from app.schemas.chat import (
    BuildPolicyChunksRequest,
    BuildPolicyChunksResponse,
    ChatAnswerRequest,
    ChatAnswerResponse,
    ChatSearchRequest,
    ChatSearchResponse,
    PolicyChunkStatsResponse,
)
from app.services.chat_rag import (
    answer_policy_question,
    build_policy_chunks,
    get_policy_chunk_stats,
    retrieve_policy_chunk_sources,
)

router = APIRouter()


@router.get(
    "/chunks/stats",
    response_model=PolicyChunkStatsResponse,
    summary="챗봇 RAG 청크/임베딩 적재 현황 조회",
)
def read_policy_chunk_stats(db: Session = Depends(get_db)):
    return get_policy_chunk_stats(db)


@router.post(
    "/chunks/build",
    response_model=BuildPolicyChunksResponse,
    summary="policy_documents 전체/일부를 policy_chunks로 청킹 및 임베딩",
)
def build_policy_chunk_embeddings(
    payload: BuildPolicyChunksRequest,
    db: Session = Depends(get_db),
):
    return build_policy_chunks(
        db=db,
        policy_id=payload.policy_id,
        limit=payload.limit,
        force=payload.force,
        provider=payload.provider,
        model_name=payload.model_name,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.post(
    "/search",
    response_model=ChatSearchResponse,
    summary="사용자 질문으로 policy_chunks 벡터 검색",
)
def search_chat_policy_chunks(
    payload: ChatSearchRequest,
    policy_id: UUID | None = Query(default=None, description="검색 범위를 제한할 정책 UUID"),
    db: Session = Depends(get_db),
):
    _ensure_policy_exists(db, policy_id)
    return retrieve_policy_chunk_sources(
        db=db,
        query=payload.query,
        limit=payload.limit,
        policy_id=policy_id,
    )


@router.post(
    "/ask",
    response_model=ChatAnswerResponse,
    summary="정책 문서 근거 기반 챗봇 답변 생성",
)
def ask_policy_chatbot(
    payload: ChatAnswerRequest,
    policy_id: UUID | None = Query(default=None, description="답변 근거를 제한할 정책 UUID"),
    db: Session = Depends(get_db),
):
    _ensure_policy_exists(db, policy_id)
    return answer_policy_question(
        db=db,
        query=payload.query,
        limit=payload.limit,
        policy_id=policy_id,
    )


def _ensure_policy_exists(db: Session, policy_id: UUID | None) -> None:
    if policy_id is None:
        return
    exists = db.query(NormalizedPolicy.id).filter(NormalizedPolicy.id == policy_id).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다.")
