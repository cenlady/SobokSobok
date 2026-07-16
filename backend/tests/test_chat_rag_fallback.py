import uuid
from unittest.mock import patch

import pytest

import app.services.chat_rag as chat_rag
from app.core.model_errors import ModelTimeoutError
from app.services.chat_rag import (
    answer_policy_question,
    build_chat_user_prompt,
    build_retrieval_only_answer,
    clean_rag_answer_text,
    clean_rag_display_text,
    clean_rag_evidence_text,
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


def test_chat_prompt_explains_legal_terms_without_inventing_missing_thresholds():
    prompt = build_chat_user_prompt(
        "지원 대상 확인",
        [
            _typed_source(
                "「소상공인기본법」에 따른 소상공인. 단, 융자제외업종은 지원 불가.",
                "eligibility",
                ["eligibility", "target"],
            )
        ],
    )

    assert "중학생도 이해할 수 있는 쉬운 한국어" in prompt
    assert "직원 수와 매출 규모 등이 법에서 정한 소상공인 기준에 맞는 작은 사업체" in prompt
    assert "정책자금 대출을 받을 수 없도록 정해진 업종" in prompt
    assert "사업을 운영한 기간" in prompt
    assert "평소 계속 고용한 직원" in prompt
    assert "직원 수·매출 기준이 없으면 숫자를 만들지 말고" in prompt
    assert "공고나 담당 기관 확인이 필요" in prompt


def test_clean_rag_display_text_hides_structured_json_noise():
    raw = (
        '{"business_age_limit": null, "employee_limit": {"constraints": '
        '[{"operator": "<", "source_text": "5인 미만", "value": 5}], '
        '"unit": "people"}, "sales_limit": null}'
    )

    cleaned = clean_rag_display_text(raw)

    assert cleaned == "5인 미만"
    assert "employee_limit" not in cleaned
    assert "source_text" not in cleaned
    assert "constraints" not in cleaned


def test_retrieval_only_answer_does_not_expose_structured_json_noise():
    raw = (
        '{"business_age_limit": null, "employee_limit": {"constraints": '
        '[{"operator": "<", "source_text": "5인 미만", "value": 5}], '
        '"unit": "people"}, "sales_limit": null}'
    )

    answer = build_retrieval_only_answer(
        "지원 대상 확인",
        [_typed_source(raw, "eligibility", ["eligibility", "target"])],
    )

    assert "5인 미만" in answer
    assert "employee_limit" not in answer
    assert "source_text" not in answer
    assert "constraints" not in answer


def test_clean_rag_answer_text_keeps_conditions_but_hides_internal_judgement_lines():
    raw = "\n".join(
        [
            "여부 판단 02 대출 신청·실행 (금융기관-방문 접수) 신용·담보 평가 후 대출",
            "5인 미만 / 10인 미만",
            "[소상공인기본법]상 소상공인 : 상시근로자 5인 미만",
            "제조업",
            "건설업",
        ]
    )

    cleaned = clean_rag_answer_text(raw)

    assert "여부 판단" not in cleaned
    assert "대출 신청" not in cleaned
    assert "5인 미만 / 10인 미만" in cleaned
    assert "상시근로자 5인 미만" in cleaned
    assert "제조업" in cleaned


def test_clean_rag_evidence_text_formats_internal_judgement_line_for_source_card():
    raw = "여부 판단 02 대출 신청·실행 (금융기관-방문 접수) 신용·담보 평가 후 대출"

    evidence = clean_rag_evidence_text(raw)

    assert "여부 판단" not in evidence
    assert "대출 신청·실행" in evidence
    assert "금융기관 방문 접수" in evidence
    assert "신용·담보 평가 후 대출" in evidence
    assert clean_rag_answer_text(raw) == ""


def test_retrieval_only_answer_hides_internal_judgement_lines_from_chat_body():
    raw = "\n".join(
        [
            "여부 판단 02 대출 신청·실행 (금융기관-방문 접수) 신용·담보 평가 후 대출",
            "5인 미만 / 10인 미만",
            "[소상공인기본법]상 소상공인 : 상시근로자 5인 미만",
            "제조업",
            "건설업",
        ]
    )

    answer = build_retrieval_only_answer(
        "지원 대상 확인",
        [_typed_source(raw, "eligibility", ["eligibility", "target"])],
    )

    assert "여부 판단" not in answer
    assert "대출 신청" not in answer
    assert "상시근로자 5인 미만" in answer


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


def test_attribute_questions_answer_only_the_requested_policy_field(monkeypatch):
    source = _source(
        "[서비스 목적] 소상공인 상담 지원 "
        "[지원 대상] 경기도 소상공인연합회 "
        "[지원 내용] 법무, 노무, 세무 상담 "
        "[신청 방법] 전화, 방문, 온라인 "
        "[구비 서류] 해당없음 "
        "[신청 기한] 상시신청 "
        "[문의처] 수원센터 031-202-8254"
    )
    source["policy_title"] = "소상공인 상담센터 운영"

    def fake_retrieve(*, query, **_kwargs):
        return {
            "query": query,
            "expanded_query": query,
            "intent_tags": chat_rag.infer_intent_tags(None, None, query),
            "response_mode": "answer",
            "candidates": [],
            "sources": [source],
        }

    def fail_if_llm_called(*_args, **_kwargs):
        raise AssertionError("단일 정책 속성 질문은 LLM 종합 요약을 호출하면 안 됩니다.")

    monkeypatch.setattr(chat_rag, "retrieve_policy_chunk_sources", fake_retrieve)
    monkeypatch.setattr(chat_rag, "generate_chat_answer", fail_if_llm_called)

    requirements = answer_policy_question(db=None, query="필요 서류 확인")
    assert "별도로 준비해야 하는 서류는 명시되어 있지 않아요" in requirements["answer"]
    assert "경기도 소상공인연합회" not in requirements["answer"]
    assert "상시 신청" not in requirements["answer"]

    deadline = answer_policy_question(db=None, query="신청 기간 확인")
    assert "신청 기간은 상시 신청이에요" in deadline["answer"]
    assert "경기도 소상공인연합회" not in deadline["answer"]
    assert "서류" not in deadline["answer"]

    eligibility = answer_policy_question(db=None, query="지원 대상 확인")
    assert "경기도 소상공인연합회" in eligibility["answer"]
    assert "상시신청" not in eligibility["answer"]
    assert "해당없음" not in eligibility["answer"]


def test_retrieval_fallback_preserves_numeric_thousands_separators():
    answer = build_retrieval_only_answer(
        "지원 대상 확인",
        [
            _typed_source(
                "○ 정책서민금융상품 이용자(미소금융, 햇살론 등) "
                "○ 저신용 영세자영업자(개인신용평점 하위 100분의 20 및 "
                "연간소득 4,500만원 이하/연간소득 3,500만원 이하)",
                "eligibility",
                ["eligibility", "target"],
            )
        ],
    )

    assert "4,500만원" in answer
    assert "3,500만원" in answer
    assert "- 500만원" not in answer


def test_policy_scoped_question_uses_parent_documents_and_llm(monkeypatch):
    policy_id = uuid.UUID("f93a0be9-3852-4645-be53-aa3203e10da9")
    parent_source = _typed_source(
        "○ 정책서민금융상품 이용자(미소금융, 햇살론 등) "
        "○ 저신용 영세자영업자(연간소득 4,500만원 이하)",
        "eligibility",
        ["eligibility", "target"],
    )
    parent_source["metadata"]["retrieval_mode"] = "parent_document"
    captured = {}

    def fake_parent_retrieve(**_kwargs):
        return {
            "query": "지원 대상 확인",
            "expanded_query": "지원 대상 확인",
            "intent_tags": ["eligibility"],
            "response_mode": "answer",
            "candidates": [],
            "sources": [parent_source],
        }

    def fail_if_chunk_search_called(**_kwargs):
        raise AssertionError("정책이 지정된 채팅에서 벡터 청크 검색을 호출하면 안 됩니다.")

    def fake_generate(query, sources, *, conversation_context="", model_mode=None):
        captured["query"] = query
        captured["sources"] = sources
        captured["conversation_context"] = conversation_context
        captured["model_mode"] = model_mode
        return "LLM이 부모 문서 원문을 읽기 쉽게 정리한 답변"

    monkeypatch.setattr(chat_rag, "retrieve_policy_document_sources", fake_parent_retrieve)
    monkeypatch.setattr(chat_rag, "retrieve_policy_chunk_sources", fail_if_chunk_search_called)
    monkeypatch.setattr(chat_rag, "generate_chat_answer", fake_generate)

    response = answer_policy_question(
        db=None,
        query="지원 대상 확인",
        policy_id=policy_id,
        model_mode="local",
    )

    assert response["answer"] == "LLM이 부모 문서 원문을 읽기 쉽게 정리한 답변"
    assert captured["query"] == "지원 대상 확인"
    assert captured["sources"] == [parent_source]
    assert captured["model_mode"] == "local"


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


def test_out_of_scope_daily_question_wins_over_small_business_background():
    response = answer_policy_question(
        db=None,
        query="나 소상공인인데, 오늘 점심 메뉴 추천해줘",
        limit=6,
    )

    assert response["intent_tags"] == ["out_of_scope"]
    assert response["sources"] == []
    assert "소상공인 정책 공고" in response["answer"]
    assert is_out_of_policy_scope("나 소상공인인데, 오늘 점심 메뉴 추천해줘") is True
    assert is_out_of_policy_scope("나 소상공인이고, 아침 메뉴 추천해줘") is True


@pytest.mark.parametrize(
    "query",
    [
        "자영업자인데 오늘 카페 추천해줘",
        "사업자인데 주말 여행지 추천해줘",
        "예비창업자인데 영화 뭐 볼까?",
        "중소기업 대표인데 운동 루틴 추천해줘",
        "청년 사업자인데 오늘 날씨 어때?",
        "프리랜서인데 강아지 키워도 될까?",
        "소상공인인데 넷플릭스에서 뭐 볼까?",
        "사업자인데 주말에 뭐 하면 좋을까?",
    ],
)
def test_daily_intent_wins_over_policy_target_background(query):
    assert is_out_of_policy_scope(query) is True


def test_policy_scope_allows_detail_context_and_policy_domain_terms():
    policy_id = uuid.UUID("def4bdcb-9e7e-4dd5-a2be-875c14345e1b")

    assert is_out_of_policy_scope("이거 요약해줘", policy_id=policy_id) is False
    assert is_out_of_policy_scope("미용실 지원금 있어?", policy_id=None) is False
    assert is_out_of_policy_scope("나는 현금으로 지급해주는 복지 받고싶어. 추천해줘", policy_id=None) is False
    assert is_out_of_policy_scope("현금으로 지급해주는 복지 추천해줘", policy_id=None) is False
    assert is_out_of_policy_scope("소상공인인데 점심 장사 지원금 신청 가능해?", policy_id=None) is False
    assert is_out_of_policy_scope("그 정책 말고 오늘 점심 뭐 먹지?", policy_id=policy_id) is True
    assert is_out_of_policy_scope("단발 가능?", policy_id=policy_id) is True


@pytest.mark.parametrize(
    "query",
    [
        "소상공인 카페 창업 지원금 신청 방법 알려줘",
        "자영업자 대상 정책자금 대출 조건이 뭐야?",
        "청년 사업자 지원사업 공고 찾아줘",
        "중소기업 세제 감면 신청 서류 알려줘",
        "소상공인인데 받을 수 있는 혜택 알려줘",
    ],
)
def test_explicit_policy_request_wins_over_daily_topic_words(query):
    assert is_out_of_policy_scope(query) is False


@patch("app.services.chat_rag.get_chat_model")
def test_chat_model_timeout_is_not_replaced_with_retrieval_fallback(mock_get_chat_model):
    mock_get_chat_model.return_value.generate.side_effect = ModelTimeoutError()

    with pytest.raises(ModelTimeoutError):
        generate_chat_answer("지원 대상이 누구야?", [_source("[지원 대상] 소상공인")])
