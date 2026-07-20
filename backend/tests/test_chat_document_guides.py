from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.services.prep_rag as prep_rag


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_conditions):
        return self

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def query(self, _model):
        return _Query(self.rows)


@pytest.mark.parametrize(
    "query",
    [
        "사업계획서에 대해 설명해줘",
        "사업 계획서는 어떻게 작성해?",
        "사업자등록증은 어디서 발급받아?",
        "지방세 완납증명서 준비 방법 알려줘",
    ],
)
def test_document_guide_questions_are_detected(query):
    assert prep_rag.is_document_guide_question(query) is True


def test_policy_search_with_document_name_is_not_hijacked():
    assert prep_rag.is_document_guide_question("사업계획서가 필요한 지원사업 찾아줘") is False
    assert prep_rag.is_document_guide_question("사업계획서가 필요한 지원사업 알려줘") is False
    assert prep_rag.is_document_guide_question("사업계획서가 필요한 공고 어떤 게 있어?") is False


def test_exact_business_plan_question_uses_verified_guide_without_vector_search(monkeypatch):
    row = SimpleNamespace(
        document_name="사업계획서",
        guide_text="사업계획서 — 본인 작성 / 공고 양식 사용",
    )
    vector_search = Mock(side_effect=AssertionError("정확한 서류명은 임베딩 검색을 호출하면 안 됩니다."))
    monkeypatch.setattr(prep_rag, "search_prep_guides", vector_search)

    resolution = prep_rag.resolve_document_guide_question(
        _Db([row]),
        "사업계획서에 대해 설명해줘",
        model_mode="cloud",
    )

    assert resolution is not None
    assert resolution.document_names == ("사업계획서",)
    assert resolution.exact is True
    assert "신청자가 직접 작성하는 문서" in resolution.answer
    assert "공고에 양식이 있으면 그것을 사용" in resolution.answer
    assert "지원 목적·사업 내용·기대 효과" in resolution.answer
    vector_search.assert_not_called()


def test_loan_application_form_is_explained_as_template_with_user_wording():
    row = SimpleNamespace(
        document_name="신청서식",
        guide_text="신청서식 — 발급 서류가 아니라 공고 양식을 내려받아 직접 작성합니다.",
    )

    resolution = prep_rag.resolve_document_guide_question(
        _Db([row]),
        "융자신청서에 대해 설명해줘",
        model_mode="cloud",
    )

    assert resolution is not None
    assert resolution.document_names == ("신청서식",)
    assert resolution.answer.startswith("융자신청서는 기관에서 발급받는 서류가 아니라")
    assert "• 양식 받는 곳: 해당 공고문 첨부파일" in resolution.answer
    assert "• 준비 방법: 공고에 첨부된 양식을 그대로 작성해 주세요." in resolution.answer
    assert "작성 시간은 별도" in resolution.answer
    assert "신청서식은" not in resolution.answer
    assert "• 방문:" not in resolution.answer
    assert "공고 기관에서 준비하거나 발급받는" not in resolution.answer


def test_document_guide_output_depends_on_preparation_type():
    issued = prep_rag.resolve_document_guide_question(
        _Db(
            [
                SimpleNamespace(
                    document_name="사업자등록증명",
                    guide_text="사업자등록증명 — 국세청에서 발급합니다.",
                )
            ]
        ),
        "사업자등록증은 어디서 발급해?",
        model_mode="cloud",
    )
    owned = prep_rag.resolve_document_guide_question(
        _Db([SimpleNamespace(document_name="신분증", guide_text="신분증 — 본인 소지")]),
        "신분증은 어떻게 준비해?",
        model_mode="cloud",
    )
    consent = prep_rag.resolve_document_guide_question(
        _Db(
            [
                SimpleNamespace(
                    document_name="개인정보수집이용동의서",
                    guide_text="공고 양식에 서명합니다.",
                )
            ]
        ),
        "개인정보 수집·이용 동의서는 어디서 받아?",
        model_mode="cloud",
    )

    assert issued is not None and "사업자등록증은 국세청에서 발급받는 서류" in issued.answer
    assert owned is not None and "신분증은 새로 발급받기보다 현재 가지고 있는 것" in owned.answer
    assert "준비 가능한 종류" in owned.answer
    assert consent is not None and "기관에서 발급받는 서류가 아니라" in consent.answer
    assert "양식 받는 곳" in consent.answer


def test_unknown_document_word_uses_prep_vector_fallback(monkeypatch):
    row = SimpleNamespace(
        document_name="표준재무제표증명",
        guide_text="표준재무제표증명 — 국세청에서 발급합니다. / 온라인: 홈택스",
    )
    monkeypatch.setattr(
        prep_rag,
        "search_prep_guides",
        Mock(return_value=[(row, 0.72)]),
    )

    resolution = prep_rag.resolve_document_guide_question(
        _Db(),
        "재무 상태를 증빙하는 문서는 어디서 발급해?",
        model_mode="local",
    )

    assert resolution is not None
    assert resolution.document_names == ("표준재무제표증명",)
    assert resolution.exact is False
    assert "가장 가까운 서류" in resolution.answer
    assert "서류명이 맞는지" in resolution.answer


def test_low_similarity_document_does_not_guess(monkeypatch):
    row = SimpleNamespace(document_name="주민등록등본", guide_text="주민센터에서 발급")
    monkeypatch.setattr(
        prep_rag,
        "search_prep_guides",
        Mock(return_value=[(row, prep_rag.PREP_VECTOR_MIN_SIMILARITY - 0.01)]),
    )

    resolution = prep_rag.resolve_document_guide_question(
        _Db(),
        "처음 보는 증빙 문서 설명해줘",
        model_mode="local",
    )

    assert resolution is None
