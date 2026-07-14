# -*- coding: utf-8 -*-
"""[서류 검토 영역] 서류별 발급 가이드 — 어디서, 어떻게, 얼마나 걸려서 떼는가.

소상공인이 지원금을 못 받는 이유는 '무슨 서류가 필요한지 몰라서'만이 아니다.
서류 이름을 알아도 '어디서 어떻게 떼는지' 몰라서 못 낸다. 목록만 던지는 건 절반이다.

── 왜 수작업인가

LLM에게 물어 생성할 수도 있지만, 발급처를 틀리게 알려주면 사장님이 헛걸음한다.
서류 검토 도구가 잘못된 정보를 주는 건 아무 정보도 안 주는 것보다 나쁘다.
그래서 확인 가능한 사실만 적는다.

── 왜 31개인가

공고에서 뽑은 서류명 411개를 정규화하면 233개가 되고, 그중 2회 이상 등장하는 31개가
전체 요구 항목의 55%를 커버한다. 나머지는 정책 하나에만 나오는 특수 서류라 일반 가이드를
쓸 수 없다(그건 공고를 봐야 한다).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentGuide:
    """서류 하나를 어떻게 발급받는가."""

    name: str
    issuer: str  # 발급 기관
    online: str | None  # 온라인 발급처 (없으면 None)
    online_url: str | None
    offline: str | None  # 방문 발급처
    duration: str  # 소요 시간
    fee: str  # 수수료
    tip: str | None = None  # 실무 팁

    def to_text(self) -> str:
        """임베딩·표시용 한 덩어리 텍스트."""
        parts = [f"{self.name} — {self.issuer}에서 발급합니다."]
        if self.online:
            parts.append(f"온라인: {self.online}")
        if self.offline:
            parts.append(f"방문: {self.offline}")
        parts.append(f"소요 시간: {self.duration}")
        parts.append(f"수수료: {self.fee}")
        if self.tip:
            parts.append(f"참고: {self.tip}")
        return " / ".join(parts)


HOMETAX = "https://www.hometax.go.kr"
GOV24 = "https://www.gov.kr"
WETAX = "https://www.wetax.go.kr"
IROS = "https://www.iros.go.kr"
FOURINS = "https://www.4insure.or.kr"


GUIDES: list[DocumentGuide] = [
    # ── 국세청 (홈택스) ──────────────────────────────────────────────
    DocumentGuide(
        name="사업자등록증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 사업자등록증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="'사업자등록증'과 '사업자등록증명'은 다른 서류입니다. 공고에서 '증명'을 요구하면 홈택스에서 새로 발급받아야 합니다.",
    ),
    DocumentGuide(
        name="소득금액증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 소득금액증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="종합소득세 신고를 마친 연도만 발급됩니다. 5월 신고 전에는 전년도 자료가 없을 수 있습니다.",
    ),
    DocumentGuide(
        name="부가가치세과세표준증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 부가가치세 과세표준증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="매출 규모를 증명할 때 가장 많이 쓰입니다.",
    ),
    DocumentGuide(
        name="부가가치세면세사업자수입금액증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 면세사업자 수입금액증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="면세사업자(학원·병원·농수산물 등)는 과세표준증명 대신 이걸 냅니다.",
    ),
    DocumentGuide(
        name="표준재무제표증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 표준재무제표증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="복식부기 의무자만 발급됩니다. 간편장부 대상자는 소득금액증명으로 대체하는 경우가 많습니다.",
    ),
    DocumentGuide(
        name="국세납세증명서",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 납세증명서",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="유효기간이 있습니다(보통 30일). 신청 직전에 떼세요.",
    ),
    DocumentGuide(
        name="휴업사실증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 휴업사실증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="폐업사실증명",
        issuer="국세청",
        online="홈택스 > 증명·등록·신청 > 폐업사실증명",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="재기·재창업 지원사업에서 요구합니다.",
    ),
    DocumentGuide(
        name="원천징수이행상황신고서",
        issuer="국세청",
        online="홈택스 > 세금신고 > 신고내역 조회에서 출력",
        online_url=HOMETAX,
        offline="세무서 민원봉사실",
        duration="온라인 즉시",
        fee="무료",
        tip="직원 고용을 증명할 때 씁니다. 제출한 신고서를 다시 출력하는 것입니다.",
    ),
    # ── 지방자치단체 (위택스) ────────────────────────────────────────
    DocumentGuide(
        name="지방세납세증명서",
        issuer="지방자치단체",
        online="위택스 > 납부결과 > 납세증명서",
        online_url=WETAX,
        offline="시·군·구청, 주민센터",
        duration="온라인 즉시",
        fee="무료",
        tip="국세납세증명서와 별개입니다. 둘 다 요구하는 공고가 많습니다.",
    ),
    # ── 행정안전부 (정부24) ──────────────────────────────────────────
    DocumentGuide(
        name="주민등록등본",
        issuer="행정안전부",
        online="정부24 > 주민등록표 등본",
        online_url=GOV24,
        offline="주민센터, 무인민원발급기",
        duration="온라인 즉시",
        fee="온라인 무료 / 방문 400원",
    ),
    DocumentGuide(
        name="주민등록초본",
        issuer="행정안전부",
        online="정부24 > 주민등록표 초본",
        online_url=GOV24,
        offline="주민센터, 무인민원발급기",
        duration="온라인 즉시",
        fee="온라인 무료 / 방문 400원",
    ),
    DocumentGuide(
        name="가족관계증명서",
        issuer="대법원",
        online="전자가족관계등록시스템",
        online_url="https://efamily.scourt.go.kr",
        offline="시·군·구청, 주민센터",
        duration="온라인 즉시",
        fee="온라인 무료 / 방문 1,000원",
        tip="'상세'와 '일반'이 다릅니다. 공고에서 요구하는 종류를 확인하세요.",
    ),
    DocumentGuide(
        name="장애인증명서",
        issuer="주민센터",
        online="정부24 > 장애인증명서",
        online_url=GOV24,
        offline="주민센터",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="한부모가족증명서",
        issuer="주민센터",
        online="정부24 > 한부모가족 증명서",
        online_url=GOV24,
        offline="주민센터",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="국민기초생활수급자증명서",
        issuer="주민센터",
        online="정부24 > 국민기초생활수급자 증명서",
        online_url=GOV24,
        offline="주민센터",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="외국인등록사실증명",
        issuer="법무부",
        online="정부24 > 외국인등록사실증명",
        online_url=GOV24,
        offline="출입국·외국인청",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="국내거소신고사실증명",
        issuer="법무부",
        online="정부24 > 국내거소신고사실증명",
        online_url=GOV24,
        offline="출입국·외국인청",
        duration="온라인 즉시",
        fee="무료",
    ),
    # ── 4대보험 ─────────────────────────────────────────────────────
    DocumentGuide(
        name="4대사회보험료완납증명서",
        issuer="4대사회보험 정보연계센터",
        online="4대사회보험 정보연계센터 > 증명서 발급",
        online_url=FOURINS,
        offline="건강보험공단·국민연금공단 지사",
        duration="온라인 즉시",
        fee="무료",
        tip="네 가지 보험을 한 장에 담아 발급합니다. 각각 떼지 않아도 됩니다.",
    ),
    DocumentGuide(
        name="고용보험료완납증명원",
        issuer="근로복지공단",
        online="고용·산재보험 토탈서비스",
        online_url="https://total.comwel.or.kr",
        offline="근로복지공단 지사",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="산재보험료완납증명원",
        issuer="근로복지공단",
        online="고용·산재보험 토탈서비스",
        online_url="https://total.comwel.or.kr",
        offline="근로복지공단 지사",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="국민연금보험료납부증명",
        issuer="국민연금공단",
        online="국민연금공단 전자민원 > 증명서 발급",
        online_url="https://minwon.nps.or.kr",
        offline="국민연금공단 지사",
        duration="온라인 즉시",
        fee="무료",
    ),
    DocumentGuide(
        name="건강보험료납부확인서",
        issuer="국민건강보험공단",
        online="건강보험 사이버민원센터",
        online_url="https://minwon.nhis.or.kr",
        offline="건강보험공단 지사",
        duration="온라인 즉시",
        fee="무료",
    ),
    # ── 법인 ────────────────────────────────────────────────────────
    DocumentGuide(
        name="법인등기사항전부증명서",
        issuer="대법원 등기소",
        online="인터넷등기소 > 등기사항증명서 발급",
        online_url=IROS,
        offline="등기소, 무인발급기",
        duration="온라인 즉시",
        fee="온라인 1,000원 / 방문 1,200원",
        tip="'말소사항 포함'을 요구하는 공고가 많습니다. 발급 시 옵션을 확인하세요.",
    ),
    DocumentGuide(
        name="법인인감증명서",
        issuer="대법원 등기소",
        online=None,
        online_url=None,
        offline="등기소 (법인인감카드 필요)",
        duration="방문 즉시",
        fee="1,000원",
        tip="온라인 발급이 안 됩니다. 법인인감카드를 챙겨 등기소에 가야 합니다.",
    ),
    # ── 신분 ────────────────────────────────────────────────────────
    DocumentGuide(
        name="신분증",
        issuer="본인 소지",
        online=None,
        online_url=None,
        offline="주민등록증·운전면허증·여권",
        duration="즉시",
        fee="무료",
        tip="사본 제출을 요구하면 앞뒤 모두 복사하세요.",
    ),
    # ── 기관 양식 (발급이 아니라 작성) ──────────────────────────────
    DocumentGuide(
        name="신청서식",
        issuer="공고 기관",
        online="해당 공고문 첨부파일",
        online_url=None,
        offline="공고 기관 방문",
        duration="즉시",
        fee="무료",
        tip="발급받는 서류가 아니라 공고에 첨부된 양식을 내려받아 작성하는 것입니다. 공고문 하단 첨부파일을 확인하세요.",
    ),
    DocumentGuide(
        name="개인정보수집이용동의서",
        issuer="공고 기관",
        online="해당 공고문 첨부파일",
        online_url=None,
        offline="공고 기관 방문",
        duration="즉시",
        fee="무료",
        tip="공고에 첨부된 양식에 서명하면 됩니다. 따로 발급받는 서류가 아닙니다.",
    ),
    DocumentGuide(
        name="사업계획서",
        issuer="본인 작성",
        online="공고에 양식이 있으면 그것을 사용",
        online_url=None,
        offline=None,
        duration="작성 시간 필요",
        fee="무료",
        tip="공고에 지정 양식이 있으면 반드시 그 양식을 써야 합니다. 자유 양식이면 지원 목적·사업 내용·기대 효과를 담으세요.",
    ),
]


# 이름 → 가이드
GUIDE_BY_NAME: dict[str, DocumentGuide] = {g.name: g for g in GUIDES}


def get_guide(document_name: str) -> DocumentGuide | None:
    """정규화된 서류명으로 발급 가이드를 찾는다. 없으면 None."""
    return GUIDE_BY_NAME.get(document_name)
