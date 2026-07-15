import uuid
from unittest.mock import patch

import pytest

from app.core.model_errors import ModelTimeoutError
from app.services.chat_rag import (
    answer_policy_question,
    build_retrieval_only_answer,
    generate_chat_answer,
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


def _typed_source(chunk_text: str, document_type: str, intent_tags: list[str]):
    source = _source(chunk_text)
    source["policy_title"] = "소상공인 특례보증"
    source["document_type"] = document_type
    source["metadata"] = {"intent_tags": intent_tags, "support_type": "현금(융자)"}
    return source


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


def test_retrieval_only_answer_prefers_required_document_sources_over_candidate_fallback():
    answer = build_retrieval_only_answer(
        "소상공인 특례보증 지원 받으려면 준비해야 되는 서류 알려줘",
        [
            _typed_source(
                "신청서 사업자등록증 사본 금융거래사실확인서 최근3년간 재무제표 부동산등기부등본",
                "requirements",
                ["requirements", "documents"],
            ),
            _typed_source(
                "광주 소재 소기업, 소상공인, 자영업자",
                "eligibility",
                ["eligibility", "target"],
            ),
            _typed_source(
                "구비서류 : 사업자등록증 사업장 및 거주주택 임차계약서",
                "requirements",
                ["requirements", "documents"],
            ),
        ],
    )

    assert "필요한 서류는 다음과 같아요" in answer
    assert "관련성이 높은 소상공인 정책 후보" not in answer
    assert "신청서" in answer
    assert "사업자등록증 사본" in answer
    assert "금융거래사실확인서" in answer
    assert "최근 3년간 재무제표" in answer
    assert "부동산등기부등본" in answer
    assert "사업장 및 거주주택 임차계약서" in answer
    assert "광주 소재" not in answer


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
    assert is_out_of_policy_scope("나는 현금으로 지급해주는 복지 받고싶어. 추천해줘", policy_id=None) is False
    assert is_out_of_policy_scope("현금으로 지급해주는 복지 추천해줘", policy_id=None) is False
    assert is_out_of_policy_scope("단발 가능?", policy_id=policy_id) is True


@patch("app.services.chat_rag.get_chat_model")
def test_chat_model_timeout_is_not_replaced_with_retrieval_fallback(mock_get_chat_model):
    mock_get_chat_model.return_value.generate.side_effect = ModelTimeoutError()

    with pytest.raises(ModelTimeoutError):
        generate_chat_answer("지원 대상이 누구야?", [_source("[지원 대상] 소상공인")])
