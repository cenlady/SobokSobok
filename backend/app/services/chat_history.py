import re
import uuid
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.chat import ChatMessage, ChatSession


VISIBLE_CHAT_ROLES = ("user", "assistant")


def _compact_text(value: str | None, *, limit: int) -> str:
    compacted = re.sub(r"\s+", " ", value or "").strip()
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[:limit].rstrip()}…"


def _policy_payload(policy: Any) -> Dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "policy_id": str(policy.id),
        "title": policy.title,
        "summary": policy.summary,
        "support_type": policy.support_type,
        "apply_end": policy.apply_end.isoformat() if policy.apply_end else None,
    }


def _visible_messages(session: ChatSession) -> List[ChatMessage]:
    messages = [message for message in session.messages if message.role in VISIBLE_CHAT_ROLES]
    role_order = {"user": 0, "assistant": 1}
    return sorted(
        messages,
        key=lambda message: (
            message.created_at.timestamp() if message.created_at else 0.0,
            role_order.get(message.role, 2),
            str(message.id or ""),
        ),
    )


def _session_payload(session: ChatSession) -> Dict[str, Any]:
    messages = _visible_messages(session)
    first_user_message = next(
        (message for message in messages if message.role == "user"),
        None,
    )
    last_assistant_message = next(
        (message for message in reversed(messages) if message.role == "assistant"),
        None,
    )
    preview_message = last_assistant_message or (messages[-1] if messages else None)
    active_policy = _policy_payload(session.active_policy)
    fallback_title = active_policy["title"] if active_policy else "새 정책 상담"

    return {
        "session_id": session.id,
        "title": _compact_text(
            first_user_message.content if first_user_message else fallback_title,
            limit=36,
        ),
        "preview": _compact_text(preview_message.content if preview_message else "", limit=72),
        "message_count": len(messages),
        "active_policy": active_policy,
        "created_at": session.created_at,
        "updated_at": session.updated_at or session.created_at,
    }


def list_user_chat_sessions(
    db: Session,
    *,
    user_id: int,
    skip: int = 0,
    limit: int = 30,
) -> Tuple[List[Dict[str, Any]], int]:
    """로그인 사용자의 실제 대화가 있는 세션만 최근 순으로 반환한다."""
    query = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .filter(ChatSession.messages.any(ChatMessage.role.in_(VISIBLE_CHAT_ROLES)))
    )
    total = query.count()
    sessions = (
        query.options(
            joinedload(ChatSession.active_policy),
            selectinload(ChatSession.messages),
        )
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_session_payload(session) for session in sessions], total


def get_user_chat_session(
    db: Session,
    *,
    user_id: int,
    session_id: uuid.UUID,
) -> Dict[str, Any]:
    """본인이 소유한 세션의 사용자·챗봇 메시지를 시간 순서대로 반환한다."""
    session = (
        db.query(ChatSession)
        .options(
            joinedload(ChatSession.active_policy),
            selectinload(ChatSession.messages).joinedload(ChatMessage.policy),
        )
        .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .one_or_none()
    )
    if session is None:
        raise ValueError("대화 기록을 찾을 수 없거나 접근 권한이 없습니다.")

    messages = []
    for message in _visible_messages(session):
        messages.append(
            {
                "message_id": message.id,
                "role": message.role,
                "content": message.content,
                "policy_id": str(message.policy_id) if message.policy_id else None,
                "policy_title": message.policy.title if message.policy else None,
                "response_mode": message.response_mode,
                "candidates": message.candidates if isinstance(message.candidates, list) else [],
                "sources": message.sources if isinstance(message.sources, list) else [],
                "created_at": message.created_at,
            }
        )

    return {
        "session": _session_payload(session),
        "messages": messages,
    }


def delete_user_chat_session(
    db: Session,
    *,
    user_id: int,
    session_id: uuid.UUID,
) -> None:
    """본인이 소유한 대화만 삭제한다. 메시지는 FK cascade로 함께 삭제된다."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .one_or_none()
    )
    if session is None:
        raise ValueError("대화 기록을 찾을 수 없거나 접근 권한이 없습니다.")
    db.delete(session)
    db.commit()
