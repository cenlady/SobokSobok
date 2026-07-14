import uuid

from app.models.chat import ChatMessage, ChatSession
from app.services.chat_rag import (
    build_policy_candidates,
    resolve_session_policy_context,
    should_request_policy_selection,
)


def _source(policy_id: str, score: float, title: str):
    return {
        "policy_id": policy_id,
        "policy_title": title,
        "similarity": score,
        "rerank_score": score,
        "apply_end": None,
        "metadata": {"policy_summary": "요약", "support_type": "지원"},
    }


def test_global_generic_question_requests_policy_selection():
    candidates = build_policy_candidates(
        [
            _source("policy-a", 0.72, "소상공인 경영안정 지원"),
            _source("policy-b", 0.70, "소상공인 금융 지원"),
        ]
    )

    assert should_request_policy_selection(
        "지원 대상이 누구야?",
        ["eligibility"],
        candidates,
        policy_id=None,
    ) is True


def test_specific_policy_name_does_not_request_selection():
    candidates = build_policy_candidates(
        [
            _source("policy-a", 0.72, "소상공인 경영안정 지원"),
            _source("policy-b", 0.70, "소상공인 금융 지원"),
        ]
    )

    assert should_request_policy_selection(
        "소상공인 경영안정 지원의 신청 기간은?",
        ["deadline"],
        candidates,
        policy_id=None,
    ) is False


def test_session_uses_selected_policy_for_short_follow_up_question():
    policy_id = uuid.uuid4()
    session = ChatSession(active_policy_id=policy_id)
    history = [ChatMessage(role="user", content="지원 대상이 누구야?")]

    assert resolve_session_policy_context(
        "서류는 뭐야?",
        session=session,
        recent_messages=history,
    ) == policy_id


def test_session_releases_selected_policy_for_new_topic():
    policy_id = uuid.uuid4()
    session = ChatSession(active_policy_id=policy_id)
    history = [ChatMessage(role="user", content="지원 대상이 누구야?")]

    assert resolve_session_policy_context(
        "다른 전기요금 지원 공고를 찾아줘",
        session=session,
        recent_messages=history,
    ) is None
