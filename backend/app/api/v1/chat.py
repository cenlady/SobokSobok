from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.chat import ChatMessage
from app.models.normalized_policy import NormalizedPolicy
from app.models.user import User
from app.schemas.chat import (
    BuildPolicyChunksRequest,
    BuildPolicyChunksResponse,
    ChatAnswerRequest,
    ChatAnswerResponse,
    ChatSearchRequest,
    ChatSearchResponse,
    ChatSessionResponse,
    PolicyChunkStatsResponse,
    SelectChatPolicyRequest,
)
from app.services.chat_rag import (
    answer_policy_question,
    build_recommendation_follow_up_answer,
    build_policy_chunks,
    get_or_create_chat_session,
    get_policy_chunk_stats,
    get_recent_chat_messages,
    record_chat_turn,
    retrieve_policy_chunk_sources,
    resolve_session_policy_context,
)

router = APIRouter()


@router.get("/chunks/stats", response_model=PolicyChunkStatsResponse)
def read_policy_chunk_stats(db: Session = Depends(get_db)):
    return get_policy_chunk_stats(db)


@router.post("/chunks/build", response_model=BuildPolicyChunksResponse)
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


@router.post("/search", response_model=ChatSearchResponse)
def search_chat_policy_chunks(
    payload: ChatSearchRequest,
    policy_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _ensure_policy_exists(db, policy_id)
    return retrieve_policy_chunk_sources(
        db=db,
        query=payload.query,
        limit=payload.limit,
        policy_id=policy_id,
    )


@router.post("/ask", response_model=ChatAnswerResponse)
def ask_policy_chatbot(
    payload: ChatAnswerRequest,
    policy_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """질문을 저장하고, 필요할 때만 이전에 선택한 공고 문맥을 이어서 답한다."""
    _ensure_policy_exists(db, policy_id)
    _ensure_policy_exists(db, payload.selected_policy_id)
    try:
        chat_session = get_or_create_chat_session(
            db,
            user_id=current_user.id,
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    recent_messages = get_recent_chat_messages(db, chat_session.id)
    recommendation_follow_up_answer = build_recommendation_follow_up_answer(
        payload.query,
        recent_messages,
    )
    if recommendation_follow_up_answer:
        response = {
            "query": payload.query,
            "expanded_query": payload.query,
            "intent_tags": ["recommendation_follow_up"],
            "response_mode": "answer",
            "candidates": [],
            "sources": [],
            "answer": recommendation_follow_up_answer,
            "langsmith_enabled": False,
            "langsmith_project": None,
        }
        record_chat_turn(
            db,
            session=chat_session,
            query=payload.query,
            answer=recommendation_follow_up_answer,
            response_mode="answer",
            context_policy_id=None,
            candidates=[],
        )
        return {
            **response,
            "session_id": chat_session.id,
            "context_policy_id": None,
            "active_policy_id": str(chat_session.active_policy_id) if chat_session.active_policy_id else None,
        }

    context_policy_id = policy_id or resolve_session_policy_context(
        payload.query,
        session=chat_session,
        recent_messages=recent_messages,
        selected_policy_id=payload.selected_policy_id,
    )
    response = answer_policy_question(
        db=db,
        query=payload.query,
        limit=payload.limit,
        policy_id=context_policy_id,
        recent_messages=recent_messages,
    )
    response_mode = response.get("response_mode", "answer")
    if context_policy_id is not None:
        chat_session.active_policy_id = context_policy_id
    elif response_mode != "out_of_scope":
        # 새 정책을 묻는 전역 질문을 처리했으면 이전 공고 고정은 해제한다.
        chat_session.active_policy_id = None

    record_chat_turn(
        db,
        session=chat_session,
        query=payload.query,
        answer=response["answer"],
        response_mode=response_mode,
        context_policy_id=context_policy_id,
        candidates=response.get("candidates") or [],
    )
    return {
        **response,
        "session_id": chat_session.id,
        "context_policy_id": str(context_policy_id) if context_policy_id else None,
        "active_policy_id": str(chat_session.active_policy_id) if chat_session.active_policy_id else None,
    }


@router.post("/sessions/{session_id}/policy", response_model=ChatSessionResponse)
def select_chat_session_policy(
    session_id: UUID,
    payload: SelectChatPolicyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """후속 질문을 특정 공고에 한정하도록 사용자가 선택한 후보를 저장한다."""
    _ensure_policy_exists(db, payload.policy_id)
    try:
        chat_session = get_or_create_chat_session(
            db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    chat_session.active_policy_id = payload.policy_id
    db.add(
        ChatMessage(
            session_id=chat_session.id,
            role="system",
            content="정책 공고 선택",
            policy_id=payload.policy_id,
        )
    )
    db.commit()
    return ChatSessionResponse(
        session_id=chat_session.id,
        active_policy_id=str(chat_session.active_policy_id),
    )


@router.delete("/sessions/{session_id}/policy", response_model=ChatSessionResponse)
def clear_chat_session_policy(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """메인 채팅의 선택 공고 문맥을 해제하고 다시 전체 정책을 검색하게 한다."""
    try:
        chat_session = get_or_create_chat_session(
            db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    chat_session.active_policy_id = None
    db.commit()
    return ChatSessionResponse(session_id=chat_session.id, active_policy_id=None)


def _ensure_policy_exists(db: Session, policy_id: UUID | None) -> None:
    if policy_id is None:
        return
    exists = db.query(NormalizedPolicy.id).filter(NormalizedPolicy.id == policy_id).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다.")
