# -*- coding: utf-8 -*-
"""LLM 서류 유형 판정 검역 테스트.

여기 케이스는 실제 사고에서 나왔다: 파이썬 학습 정리 PDF가 정책 제목을 베낀
'지방세 불복청구 선정대리인 무료지원 신청 서류'로 판정돼 요건 '선정대리인 신청서'와
0.64로 매칭 — 가짜 '충족'이 화면에 떴다. 같은 파일이 고른 정책에 따라 유형이
바뀌는 것으로 프롬프트 오염을 확정했다.
"""

import pytest

from app.services.review_documents import _sanitize_document_type

POLICY = "지방세 불복청구 선정대리인 무료지원"


class TestPolicyTitleParroting:
    """정책 제목을 베낀 유형명은 본문에서 확인될 때만 인정한다."""

    def test_본문에_없는_정책제목_베끼기는_unknown(self):
        # 실사고: 파이썬 정리 PDF인데 유형이 정책 제목 + '신청 서류'로 나왔다.
        assert _sanitize_document_type(
            "지방세 불복청구 선정대리인 무료지원 신청 서류",
            POLICY,
            "파이썬 비동기 프로그래밍은 async/await 키워드를 사용한다...",
        ) == "unknown"

    def test_진짜_서식은_본문에_양식명이_있으므로_인정한다(self):
        # 실제 신청서 파일이라면 양식 제목이 본문에 그대로 적혀 있다.
        assert _sanitize_document_type(
            "지방세 불복청구 선정대리인 무료지원 신청 서류",
            POLICY,
            "[별지 제1호] 지방세 불복청구 선정대리인 무료지원 신청 서류 성명: 연락처:",
        ) == "지방세 불복청구 선정대리인 무료지원 신청 서류"

    def test_공백_차이는_무시하고_대조한다(self):
        assert _sanitize_document_type(
            "지방세 불복청구 선정대리인 무료지원 신청서",
            POLICY,
            "지방세불복청구 선정대리인무료지원신청서 (서명란)",
        ) == "지방세 불복청구 선정대리인 무료지원 신청서"

    def test_정책과_무관한_유형명은_본문_확인_없이_통과한다(self):
        # 정책 제목을 베끼지 않은 평범한 판정은 그대로 쓴다.
        assert _sanitize_document_type("사업자등록증", POLICY, "요약 텍스트") == "사업자등록증"

    def test_정책이_없으면_베끼기_검사도_없다(self):
        assert _sanitize_document_type("선정대리인 신청서", None, "") == "선정대리인 신청서"


class TestHedgingAndGenerics:
    """추정 표현과 정체 불명 일반명은 unknown으로 되돌린다."""

    def test_괄호_추정_접미어를_벗긴다(self):
        # 실사고: "소상공인 무료법률구조 신청 서류 (추정)" 처럼 괄호 부연이 붙어 나온다.
        assert _sanitize_document_type("사업자등록증 (추정)", None, "") == "사업자등록증"

    def test_괄호를_벗겨도_추정이_남으면_unknown(self):
        assert _sanitize_document_type("추정: 신청 관련 서류", None, "") == "unknown"

    def test_일반명은_unknown(self):
        # 실사고: "정책 신청 서류 (지방세 불복청구 ... 관련)" → 괄호 제거 후 "정책 신청 서류".
        assert _sanitize_document_type(
            "정책 신청 서류 (지방세 불복청구 선정대리인 무료지원 신청 관련)", POLICY, ""
        ) == "unknown"
        assert _sanitize_document_type("신청서", None, "") == "unknown"
        assert _sanitize_document_type("문서", None, "") == "unknown"

    def test_빈_값과_unknown은_unknown(self):
        assert _sanitize_document_type("", None, "") == "unknown"
        assert _sanitize_document_type("unknown", None, "") == "unknown"
        assert _sanitize_document_type("Unknown", None, "") == "unknown"
