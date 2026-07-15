from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.chat import router
from app.core.database import get_db
from app.core.deps import get_current_user


USER_ID = 77


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
    return TestClient(app)


def _session(session_id):
    now = datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc)
    return {
        "session_id": session_id,
        "title": "서울 소상공인 지원 정책 알려줘",
        "preview": "서울에서 신청할 수 있는 정책을 정리했어요.",
        "message_count": 2,
        "active_policy": None,
        "created_at": now,
        "updated_at": now,
    }


def test_list_chat_history_returns_only_current_users_sessions():
    session_id = uuid4()
    with patch(
        "app.api.v1.chat.list_user_chat_sessions",
        return_value=([_session(session_id)], 1),
    ) as list_history:
        response = _client().get("/chat/sessions?skip=0&limit=20")

    assert response.status_code == 200
    assert response.json()["items"][0]["session_id"] == str(session_id)
    assert response.json()["items"][0]["title"] == "서울 소상공인 지원 정책 알려줘"
    list_history.assert_called_once_with(ANY, user_id=USER_ID, skip=0, limit=20)


def test_read_chat_history_restores_messages_and_sources():
    session_id = uuid4()
    message_id = uuid4()
    payload = {
        "session": _session(session_id),
        "messages": [
            {
                "message_id": message_id,
                "role": "assistant",
                "content": "필요한 서류는 사업자등록증이에요.",
                "policy_id": None,
                "policy_title": None,
                "response_mode": "answer",
                "candidates": [],
                "sources": [{"policy_id": "policy-a", "chunk_text": "사업자등록증"}],
                "created_at": datetime(2026, 7, 15, 10, 31, tzinfo=timezone.utc),
            }
        ],
    }
    with patch("app.api.v1.chat.get_user_chat_session", return_value=payload) as get_history:
        response = _client().get(f"/chat/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["messages"][0]["content"] == "필요한 서류는 사업자등록증이에요."
    assert response.json()["messages"][0]["sources"][0]["chunk_text"] == "사업자등록증"
    get_history.assert_called_once_with(ANY, user_id=USER_ID, session_id=session_id)


def test_read_chat_history_hides_missing_or_other_users_session():
    session_id = uuid4()
    with patch(
        "app.api.v1.chat.get_user_chat_session",
        side_effect=ValueError("대화 기록을 찾을 수 없거나 접근 권한이 없습니다."),
    ):
        response = _client().get(f"/chat/sessions/{session_id}")

    assert response.status_code == 404


def test_delete_chat_history_checks_owner_and_returns_no_content():
    session_id = uuid4()
    with patch("app.api.v1.chat.delete_user_chat_session") as delete_history:
        response = _client().delete(f"/chat/sessions/{session_id}")

    assert response.status_code == 204
    assert response.content == b""
    delete_history.assert_called_once_with(ANY, user_id=USER_ID, session_id=session_id)
