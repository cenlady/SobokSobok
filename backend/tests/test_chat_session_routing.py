import uuid

from app.models.chat import ChatMessage, ChatSession
from app.services.chat_rag import (
    build_conversation_context,
    build_policy_candidates,
    build_recommendation_follow_up_answer,
    is_recommendation_follow_up_question,
    latest_recommendation_candidates,
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


def test_client_selected_policy_restores_context_for_natural_follow_up_question():
    policy_id = uuid.uuid4()
    session = ChatSession(active_policy_id=None)

    assert resolve_session_policy_context(
        "이 복지를 신청하려면 준비해야 되는 서류 알려줘",
        session=session,
        recent_messages=[],
        selected_policy_id=policy_id,
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


def test_recommendation_follow_up_detects_region_challenge():
    recommended_policy_id = uuid.uuid4()
    history = [
        ChatMessage(
            role="assistant",
            content="사장님 조건과 가까운 정책 1건을 찾았어요.",
            response_mode="recommendation",
            candidates=[
                {
                    "policy_id": str(recommended_policy_id),
                    "title": "경기도 소상공인 지원",
                    "match_status": "needs_review",
                    "profile_region": {"sido": "서울특별시", "sigungu": "마포구"},
                    "warnings": ["지역 조건 확인 필요"],
                }
            ],
        )
    ]

    assert latest_recommendation_candidates(history)[0]["policy_id"] == str(recommended_policy_id)
    assert is_recommendation_follow_up_question(
        "나는 서울에 사는데 왜 경기도를 추천해줘?",
        history,
    ) is True

    answer = build_recommendation_follow_up_answer(
        "나는 서울에 사는데 왜 경기도를 추천해줘?",
        history,
    )

    assert answer is not None
    assert "서울특별시 마포구" in answer
    assert "경기도 소상공인 지원" in answer
    assert "지역 조건" in answer


def test_recommendation_follow_up_requires_saved_recommendation_context():
    assert is_recommendation_follow_up_question(
        "나는 서울에 사는데 왜 경기도를 추천해줘?",
        [],
    ) is False


def test_conversation_context_includes_recommendation_titles_and_profile_region():
    history = [
        ChatMessage(role="user", content="맞춤 정책 추천해줘"),
        ChatMessage(
            role="assistant",
            content="사장님 조건과 가까운 정책 1건을 찾았어요.",
            response_mode="recommendation",
            candidates=[
                {
                    "policy_id": str(uuid.uuid4()),
                    "title": "서울 소상공인 지원",
                    "profile_region": {"sido": "서울특별시", "sigungu": "마포구"},
                }
            ],
        ),
    ]

    context = build_conversation_context(history)

    assert "맞춤 정책 추천해줘" in context
    assert "서울 소상공인 지원" in context
    assert "서울특별시 마포구" in context
