import uuid

from app.services.chat_rag import (
    answer_policy_question,
    build_retrieval_only_answer,
    is_out_of_policy_scope,
)


def _source(chunk_text: str):
    return {
        "policy_title": "소상공인 손실보상금 지원",
        "document_type": "body",
        "document_title": "공고문",
        "chunk_text": chunk_text,
        "similarity": 0.55,
        "metadata": {"intent_tags": ["general"]},
    }


def test_retrieval_only_answer_focuses_on_eligibility_section():
    answer = build_retrieval_only_answer(
        "지원 대상이 누구야?",
        [
            _source(
                "[서비스 목적] 코로나 손실보상 "
                "[지원 대상] 코로나시기 집합금지 및 영업시간 제한 이행 소상공인 또는 "
                "중소기업기본법상 소기업 또는 연매출 30억원 이하 중기업 "
                "[지원 내용] 손실보상 지원"
            )
        ],
    )

    assert "지원 대상은 다음과 같아요" in answer
    assert "- 코로나시기 집합금지 및 영업시간 제한 이행 소상공인" in answer
    assert "LLM 답변 생성" not in answer
    assert "유사도" not in answer


def test_retrieval_only_answer_focuses_on_required_documents_section():
    answer = build_retrieval_only_answer(
        "필요한 서류가 뭐야?",
        [_source("[지원 대상] 소상공인 [구비 서류] 사업자등록증, 매출 증빙, 신청서")],
    )

    assert "필요한 서류는 다음과 같아요" in answer
    assert "- 사업자등록증" in answer
    assert "- 매출 증빙" in answer
    assert "- 신청서" in answer
    assert "document_type" not in answer


def test_out_of_scope_weather_question_does_not_search_policy_chunks():
    response = answer_policy_question(
        db=None,
        query="오늘 날씨 어때?",
        limit=6,
    )

    assert response["intent_tags"] == ["out_of_scope"]
    assert response["sources"] == []
    assert "날씨는 제가 정확히 확인해드릴 수 없어요" in response["answer"]
    assert "공고문에서 가장 가까운 내용" not in response["answer"]


def test_out_of_scope_personal_style_question_does_not_search_policy_chunks():
    response = answer_policy_question(
        db=None,
        query="나 머리 단발할까 기를까?",
        limit=6,
    )

    assert response["intent_tags"] == ["out_of_scope"]
    assert response["sources"] == []
    assert "소상공인 정책 공고" in response["answer"]


def test_policy_scope_allows_detail_context_and_policy_domain_terms():
    policy_id = uuid.UUID("def4bdcb-9e7e-4dd5-a2be-875c14345e1b")

    assert is_out_of_policy_scope("이거 요약해줘", policy_id=policy_id) is False
    assert is_out_of_policy_scope("미용실 지원금 있어?", policy_id=None) is False
    assert is_out_of_policy_scope("단발 가능?", policy_id=policy_id) is True
