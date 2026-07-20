# -*- coding: utf-8 -*-
"""서류명 정규화 테스트.

여기서 다루는 케이스는 전부 실제 공고 데이터에서 나온 것이다.
특히 '사' 버그(사업자등록증 → 업자등록증)는 한 번 실제로 냈던 실수라 회귀 테스트로 남긴다.
"""

import pytest

from app.services.document_names import (
    canonicalize,
    find_canonical_name_matches_in_text,
    find_canonical_names_in_text,
)


class TestBulletStripping:
    """글머리 기호를 지우되, 서류명의 첫 글자를 지우면 안 된다."""

    def test_한글_글머리를_서류명_첫글자로_오인하지_않는다(self):
        # '사업자등록증'의 '사'를 글머리(가·나·다·…·사)로 오인해 '업자등록증'으로
        # 만들어버린 적이 있다. 실제로 64건이 그렇게 깨졌다.
        assert canonicalize("사업자등록증") == ["사업자등록증명"]
        assert canonicalize("사업계획서") == ["사업계획서"]

    def test_진짜_한글_글머리는_지운다(self):
        # '가.' '나)' 처럼 마침표나 괄호가 따라올 때만 글머리다.
        assert canonicalize("가. 사업자등록증") == ["사업자등록증명"]
        assert canonicalize("나) 소득금액증명") == ["소득금액증명"]

    def test_기호_글머리를_지운다(self):
        assert canonicalize("⚪사업자등록증 사본") == ["사업자등록증명"]
        assert canonicalize("③ 가족관계증명서") == ["가족관계증명서"]
        assert canonicalize("- 소득금액증명") == ["소득금액증명"]

    def test_서식_번호를_지운다(self):
        assert canonicalize("[서식1] 참여신청서") == ["신청서식"]


class TestQuantifiers:
    """'사본', '1부' 같은 수량·형태 수식어는 서류의 정체와 무관하다."""

    def test_사본_1부를_지운다(self):
        assert canonicalize("사업자등록증 사본 1부.") == ["사업자등록증명"]
        assert canonicalize("사업자등록증 사본") == ["사업자등록증명"]

    def test_괄호_부연을_지운다(self):
        assert canonicalize("사업자등록증 사본 1부(기존사업자)") == ["사업자등록증명"]
        assert canonicalize("표준재무제표증명(개인)") == ["표준재무제표증명"]

    def test_또는_절은_앞엣것만_취한다(self):
        assert canonicalize("사업자등록증명 또는 사업자등록증명원(최근1개월)") == ["사업자등록증명"]


class TestSplitting:
    """한 항목에 여러 서류가 뭉쳐 있으면 쪼갠다. 다만 서류명 안의 쉼표는 쪼개면 안 된다."""

    def test_여러_서류가_뭉친_항목을_쪼갠다(self):
        result = canonicalize("지원신청서, 장애인증명서, 사업자등록 사실증명")
        assert "장애인증명서" in result
        assert "사업자등록증명" in result

    def test_서류명_안의_쉼표는_쪼개지_않는다(self):
        # "개인" / "기업 정보 등 수집" / "이용" / "제공" 은 서류가 아니다.
        # 쪼개면 "이용 동의서", "제공 동의서" 같은 파편이 생긴다(실제로 10건 생겼다).
        result = canonicalize("개인, 기업 정보 등 수집, 이용, 제공, 조회 동의서")
        assert result == ["개인정보수집이용동의서"]


class TestPlaceholders:
    """서류명이 아닌 것은 버린다. '신청서'에 '어디서 발급받나요?'는 답이 없는 질문이다."""

    @pytest.mark.parametrize(
        "raw", ["신청서", "구비서류", "제출서류", "신청인 제출서류", "신청서 등", "기타"]
    )
    def test_카테고리_플레이스홀더를_버린다(self, raw):
        assert canonicalize(raw) == []

    def test_잘린_문장을_버린다(self):
        assert canonicalize("※ 면세사업자는 사업장현황신고 기한(2/") == []

    def test_빈_입력을_버린다(self):
        assert canonicalize("") == []
        assert canonicalize("   ") == []


class TestCanonicalMapping:
    """표기가 갈라진 같은 서류를 하나로 모은다."""

    @pytest.mark.parametrize(
        "raw",
        [
            "사업자등록증",
            "사업자등록증명원",
            "사업자등록증 사본",
            "사업자 등록증",  # 공백만 다르다
            "공급업체 사업자등록증 사본 1부",
        ],
    )
    def test_사업자등록증_계열은_하나로_모인다(self, raw):
        assert canonicalize(raw) == ["사업자등록증명"]

    @pytest.mark.parametrize(
        "raw", ["부가가치세과세표준증명", "부가가치세 과세표준증명", "부가가치세 과세표준 증명원"]
    )
    def test_부가세_과세표준증명_계열(self, raw):
        assert canonicalize(raw) == ["부가가치세과세표준증명"]

    @pytest.mark.parametrize("raw", ["지방세납세증명서", "지방세 완납증명서"])
    def test_지방세_납세증명_계열(self, raw):
        assert canonicalize(raw) == ["지방세납세증명서"]

    @pytest.mark.parametrize("raw", ["지원신청서", "융자신청서", "사업포기신청서", "참여신청서"])
    def test_신청_서식류는_하나로_모인다(self, raw):
        # 이름이 무한히 갈라지는데 안내 내용은 같다 — "공고문 첨부파일에서 양식을 받으세요".
        assert canonicalize(raw) == ["신청서식"]


class TestNoDuplicates:
    def test_같은_서류가_두_번_나오면_한_번만_돌려준다(self):
        assert canonicalize("사업자등록증, 사업자등록증 사본") == ["사업자등록증명"]


class TestNaturalLanguageDocumentNameSearch:
    def test_질문_문장_안의_사업계획서를_찾는다(self):
        assert find_canonical_names_in_text("사업계획서에 대해 설명해줘") == ["사업계획서"]

    def test_별칭도_표준_서류명으로_찾는다(self):
        assert find_canonical_names_in_text("사업자등록증은 어디서 발급해?") == ["사업자등록증명"]

    def test_질문에_쓴_이름과_내부_표준명을_함께_돌려준다(self):
        assert find_canonical_name_matches_in_text("융자신청서에 대해 설명해줘") == [
            ("융자신청서", "신청서식")
        ]
        assert find_canonical_name_matches_in_text(
            "개인정보 수집·이용 동의서는 어디서 받아?"
        ) == [("개인정보 수집·이용 동의서", "개인정보수집이용동의서")]

    def test_허용된_서류만_찾는다(self):
        assert find_canonical_names_in_text(
            "사업계획서와 사업자등록증을 준비해야 해",
            allowed_names={"사업계획서"},
        ) == ["사업계획서"]
