import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.model_errors import public_model_error
from app.core.model_provider import get_user_model_mode
from app.models.chat import ChatMessage
from app.models.normalized_policy import NormalizedPolicy
from app.models.user import User
from app.schemas.chat import (
    BuildPolicyChunksRequest,
    BuildPolicyChunksResponse,
    ChatAnswerRequest,
    ChatAnswerResponse,
    ChatHistoryDetailResponse,
    ChatHistoryListResponse,
    ChatSearchRequest,
    ChatSearchResponse,
    ChatSessionResponse,
    PolicyChunkStatsResponse,
    SelectChatPolicyRequest,
)
from app.services.chat_history import (
    delete_user_chat_session,
    get_user_chat_session,
    list_user_chat_sessions,
)
from app.services.chat_graph import run_policy_chat, stream_policy_chat
from app.services.chat_rag import (
    build_policy_chunks,
    get_or_create_chat_session,
    get_policy_chunk_stats,
    get_recent_chat_messages,
    retrieve_policy_chunk_sources,
)

router = APIRouter()


@router.get("/sessions", response_model=ChatHistoryListResponse)
def list_chat_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """로그인 사용자의 대화 목록을 최근 대화 순서로 반환한다."""
    items, total = list_user_chat_sessions(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return ChatHistoryListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        has_next=skip + len(items) < total,
    )


@router.get("/sessions/{session_id}", response_model=ChatHistoryDetailResponse)
def read_chat_history(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """본인이 소유한 대화의 질문과 답변을 다시 불러온다."""
    try:
        return get_user_chat_session(
            db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_history(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """본인이 소유한 대화와 그 메시지를 삭제한다."""
    try:
        delete_user_chat_session(
            db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.post("/search", response_model=ChatSearchResponse)
def search_chat_policy_chunks(
    payload: ChatSearchRequest,
    policy_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_policy_exists(db, policy_id)
    return retrieve_policy_chunk_sources(
        db=db,
        query=payload.query,
        limit=payload.limit,
        policy_id=policy_id,
        model_mode=get_user_model_mode(current_user, "chat"),
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
    return run_policy_chat(
        db=db,
        query=payload.query,
        limit=payload.limit,
        requested_policy_id=policy_id,
        selected_policy_id=payload.selected_policy_id,
        session=chat_session,
        recent_messages=recent_messages,
        model_mode=get_user_model_mode(current_user, "chat"),
    )


@router.post("/ask/stream")
def ask_policy_chatbot_stream(
    payload: ChatAnswerRequest,
    policy_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """검색 근거는 먼저 보내고, AI 답변은 SSE 토큰으로 이어서 보낸다."""
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
    model_mode = get_user_model_mode(current_user, "chat")

    def stream_events():
        try:
            for graph_event in stream_policy_chat(
                db=db,
                query=payload.query,
                limit=payload.limit,
                requested_policy_id=policy_id,
                selected_policy_id=payload.selected_policy_id,
                session=chat_session,
                recent_messages=recent_messages,
                model_mode=model_mode,
            ):
                yield _sse(graph_event["event"], graph_event["data"])
        except Exception as exc:
            error_code, public_message = public_model_error(exc)
            yield _sse("error", {"error_code": error_code, "message": public_message})

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
