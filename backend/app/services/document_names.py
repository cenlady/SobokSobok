# -*- coding: utf-8 -*-
"""[서류 검토 영역] 공고에서 뽑아낸 필수서류 이름을 정리한다.

공고 원문에서 긁어온 서류명은 그대로 쓸 수 없다. 실측하면 이렇다.

    전체 항목      510건
    고유 서류명    411건   ← 91%가 딱 한 번만 등장. 극단적 롱테일처럼 보인다.

그런데 진짜 롱테일이 아니라 '표기가 갈라진 것'이다.

    사업자등록증 / 사업자등록증 사본 / 사업자등록증명 / 사업자등록증명원 /
    사업자등록증 사본 1부(기존사업자) / 공급업체 사업자등록증 사본 1부 / ...
    → 7가지 이름, 44건. 실제로는 서류 한 종류.

여기에 서류명이 아닌 것도 섞여 있다.

    "신청서"(16), "구비서류"(3), "신청인 제출서류"(7)        → 카테고리·플레이스홀더
    "지원신청서, 장애인증명서, 사업자등록 사실증명, ..."     → 4개가 한 항목에 뭉침(19%)

이걸 정리하지 않으면
  - 발급 가이드(prep_vectors)를 서류 하나당 일곱 번 써야 하고,
  - 요건 대조에서 '사업자등록증'과 '사업자등록증 사본'이 다른 요건으로 잡혀
    한 파일이 하나만 커버하게 된다(1:1 배정이므로).
"""

from __future__ import annotations

import re
from collections.abc import Collection

# ── 항목을 쪼개는 구분자 ─────────────────────────────────────────────
#
# 쉼표를 무조건 쪼개면 안 된다. 서류명 '안'에 쉼표가 있는 경우가 있다.
#
#     "개인, 기업 정보 등 수집, 이용, 제공, 조회 동의서"   ← 이건 서류 하나다
#     "지원신청서, 장애인증명서, 사업자등록 사실증명"       ← 이건 서류 셋이다
#
# 차이는 '각 조각이 서류명처럼 끝나는가'다. 서류는 대개 증/서/원/표/장/부로 끝난다.
# 그래서 일단 쪼갠 뒤, 조각이 서류명 꼴이 아니면 앞 조각에 도로 붙인다.
_SPLIT = re.compile(r"[,;·/]|\s+및\s+|\s+와\s+|\s+과\s+")

# 서류명은 대개 이 글자들로 끝난다. 조각이 서류인지 아닌지 가르는 데 쓴다.
_DOC_TAIL = re.compile(r"(증|증서|증명|증명서|증명원|서|원|표|장|부|류|안|첩)$")

# ── 지워야 할 것들 ───────────────────────────────────────────────────

# 글머리 기호·서식 번호. 정보가 없다.
#
# 주의: 한글 글머리(가·나·다…)를 그냥 문자 클래스에 넣으면 안 된다. "사업자등록증"의
# '사'를 글머리로 오인해 "업자등록증"으로 만들어버린다(실제로 64건이 그렇게 깨졌다).
# 한글 글머리는 '가.' '나)' 처럼 마침표나 괄호가 따라올 때만 글머리다.
_LEADING_NOISE = re.compile(
    r"^(?:[\s\-•·※○●▶▷□■◆◇*~★☆⚪⚫①②③④⑤⑥⑦⑧⑨⑩㉠㉡]|"
    r"[가-힣][.)]\s|"  # 가. 나) 다.
    r"\d+[.)]\s|"  # 1. 2)
    r"\[[^\]]*\]|"  # [서식1]
    r"\([^)]*서식[^)]*\)"  # (별지 제1호 서식)
    r")*\s*"
)

# 수량·형태 수식어. 서류의 정체와 무관하다.
_QUANTIFIER = re.compile(
    r"\s*(사본|원본|정본|각\s*\d+부|\d+\s*부|1통|각각|해당\s*시|해당자|필수|선택)\s*"
)

# 괄호 안 부연. "(기존사업자)", "(최근1개월)", "(개인)", "(법인)" 등.
# 다만 괄호가 서류명의 일부인 경우가 있어(예: "(국세)납세증명서") 앞에 글자가 없으면 남긴다.
_PAREN = re.compile(r"(?<=\S)\s*\([^)]*\)")

# "A 또는 B" → A만 취한다. 둘 다 같은 서류의 다른 이름인 경우가 대부분.
_OR_CLAUSE = re.compile(r"\s*(또는|혹은|내지)\s+.*$")

# 문장 끝 잔여물
_TRAILING = re.compile(r"[\s.。,·]+$")

# ── 서류명이 아닌 것 ─────────────────────────────────────────────────
#
# 카테고리·플레이스홀더는 발급 가이드를 만들 수 없다. 요건 대조에서도 무의미하다.
# "신청서"에 대해 "어디서 발급받나요?"는 답이 없는 질문이다.
_PLACEHOLDERS = {
    "신청서",
    "신청서 등",
    "구비서류",
    "제출서류",
    "필수서류",
    "증빙서류",
    "관련서류",
    "첨부서류",
    "신청인 제출서류",
    "기타",
    "기타서류",
    "해당서류",
    "공통",
    "공통서류",
}

# 문장이지 서류명이 아닌 것들을 걸러내는 기준
_MAX_NAME_LEN = 40
_MIN_NAME_LEN = 3


# ── 표준명 매핑 ──────────────────────────────────────────────────────
#
# 정규화 후에도 같은 서류가 다른 이름으로 남는다. 그걸 하나로 모은다.
# 발급처가 같은 것끼리 묶는 게 기준이다 — 결국 "어디서 떼나"를 알려주려는 것이므로.
_CANONICAL: dict[str, str] = {}


def _alias(canonical: str, *aliases: str) -> None:
    """표준명과 그 별칭들을 등록한다.

    공백을 뗀 형태로도 함께 넣는다. 공고마다 '사업자등록증'과 '사업자 등록증'을
    섞어 쓰는데, 사람에겐 같은 서류다.
    """
    for name in (canonical, *aliases):
        _CANONICAL[name] = canonical
        _CANONICAL[name.replace(" ", "")] = canonical


# 사업자 관련
_alias(
    "사업자등록증명",
    "사업자등록증",
    "사업자등록증명원",
    "사업자등록사실증명",
    "사업자등록 사실증명",
    "사업자등록증사본",
)
_alias("휴업사실증명", "휴업사실증명원")
_alias("폐업사실증명", "폐업사실증명원", "폐업증명")

# 국세청
_alias("소득금액증명", "소득금액증명원")
_alias(
    "부가가치세과세표준증명",
    "부가가치세 과세표준증명",
    "부가가치세 과세표준 증명원",
    "부가가치세과세표준증명원",
    "부가세과세표준증명",
)
_alias(
    "부가가치세면세사업자수입금액증명",
    "면세사업자수입금액증명",
    "면세사업자수입금액증명원",
    "부가가치세 면세사업자 수입금액 증명원",
    "수입금액증명",
    "수입금액증명원",
)
_alias("표준재무제표증명", "표준재무제표증명원")
_alias("국세납세증명서", "(국세)납세증명서", "국세완납증명서", "납세증명서")
_alias("원천징수이행상황신고서", "월별 원천징수이행상황신고서")

# 지방자치단체
_alias(
    "지방세납세증명서",
    "지방세 납세증명서",
    "지방세완납증명서",
    "지방세 완납증명서",
    "지방세납세완납증명서",
)

# 행정안전부 / 주민센터
_alias("주민등록등본", "주민등록표등본")
_alias("주민등록초본", "주민등록표초본")
_alias("가족관계증명서", "가족관계증명")

# 4대보험
_alias("4대사회보험료완납증명서", "4대보험료완납증명서", "사회보험료완납증명서")
_alias("고용보험료완납증명원", "고용보험완납증명원", "고용보험료완납증명서")
_alias("산재보험료완납증명원", "산재보험완납증명원", "산재보험료완납증명서")
_alias("국민연금보험료납부증명", "사업장국민연금보험료월별납부증명")
_alias("건강보험료납부확인서", "건강보험납부확인서")

# 법인
_alias("법인등기사항전부증명서", "법인등기사항전부증명", "법인등기부등본")
_alias("법인인감증명서", "법인인감증명")

# 기타 증명
_alias("장애인증명서", "장애인등록증")
_alias("한부모가족증명서", "한부모가족확인서")
_alias("국민기초생활수급자증명서", "기초생활수급자증명서", "수급자증명서")
_alias("외국인등록사실증명", "외국인등록증")
_alias("국내거소신고사실증명", "국내거소신고증")
_alias("신분증", "신분증 사본", "주민등록증", "운전면허증")

# 동의서류.
#
# 이름이 제각각인데 다 같은 것이다. 그리고 쉼표를 무조건 쪼개면 안 되는 대표 케이스다.
#   "개인, 기업 정보 등 수집, 이용, 제공, 조회 동의서"  → 서류 하나
# 쪼개면 "이용 동의서", "제공 동의서" 같은 파편이 생긴다(실제로 10건 생겼다).
_alias(
    "개인정보수집이용동의서",
    "개인정보 수집 이용에 관한 동의서",
    "개인정보 등 수집 이용에 관한 동의서",
    "개인정보 수집 이용 제3자 제공 동의서",
    "개인정보 수집·이용 동의서",
    "개인정보 수집이용동의서",
    "개인정보 수집 및 이용 동의서",
    "개인정보동의서",
    "개인신용정보 수집이용에 관한 동의서",
    "이용 동의서",
    "이용에 관한 동의서",
    "제공 동의서",
    "조회 동의서",
    "정보 활용 동의서",
    "수집 동의서",
    "동의서",
)

# 신청 서식류. 발급받는 게 아니라 기관 양식을 받아 작성하는 것들.
# 이름이 무한히 갈라지므로(융자신청서, 지원금 신청서, 사업포기신청서…) 하나로 모은다.
# 어차피 안내 내용이 같다 — "공고문 첨부파일에서 양식을 내려받으세요".
_alias("사업계획서", "사업 계획서", "추진계획서", "사업추진계획서")
_alias(
    "신청서식",
    "지원신청서",
    "사업신청서",
    "참여신청서",
    "대여신청서",
    "융자신청서",
    "지원금 신청서",
    "사업포기신청서",
    "신용보증 신청서",
    "참여확약서",
    "체크리스트",
)

# 공급업체 등 제3자의 서류도 결국 같은 서류다. 발급처가 같다.
_alias("사업자등록증명", "공급업체 사업자등록증", "공급업체 사업자등록증명")
_alias("신분증", "공동대표 신분증", "대표자 신분증")


def canonicalize(raw: str) -> list[str]:
    """공고에서 뽑은 서류 항목 하나를 표준 서류명 목록으로 바꾼다.

    한 항목에 여러 서류가 뭉쳐 있으면 여러 개를 돌려주고, 서류명이 아니면 빈 목록을
    돌려준다.

    >>> canonicalize("사업자등록증 사본 1부.")
    ['사업자등록증명']
    >>> canonicalize("지원신청서, 장애인증명서, 사업자등록 사실증명")
    ['장애인증명서', '사업자등록증명']
    >>> canonicalize("개인, 기업 정보 등 수집, 이용, 제공, 조회 동의서")
    ['개인정보수집이용동의서']
    >>> canonicalize("신청서")
    []
    """
    if not raw or not raw.strip():
        return []

    results: list[str] = []
    for piece in _split_items(raw):
        name = _clean(piece)
        if not _is_document_name(name):
            continue
        # 공백 유무를 가리지 않고 표준명을 찾는다.
        # 공고마다 '사업자등록증'과 '사업자 등록증'을 섞어 쓴다.
        canonical = _CANONICAL.get(name) or _CANONICAL.get(name.replace(" ", "")) or name
        results.append(canonical)

    # 순서를 유지하며 중복 제거
    seen: set[str] = set()
    unique: list[str] = []
    for name in results:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _split_items(raw: str) -> list[str]:
    """항목을 쪼갠다. 서류명 안의 쉼표를 잘못 쪼개지 않도록 되붙인다."""
    parts = [p.strip() for p in _SPLIT.split(raw) if p.strip()]
    if len(parts) <= 1:
        return parts

    merged: list[str] = []
    for part in parts:
        stripped = _TRAILING.sub("", _QUANTIFIER.sub(" ", part)).strip()
        # 서류명 꼴로 끝나지 않는 조각은 서류가 아니라 앞 서류명의 일부다.
        #   "개인" / "기업 정보 등 수집" / "이용" / "제공" / "조회 동의서"
        #   → 마지막 조각만 서류명 꼴이므로 전부 하나로 되붙는다.
        if merged and not _DOC_TAIL.search(stripped):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)

    # 되붙인 결과의 마지막 조각이 서류명 꼴이 아니면, 그 앞과도 합친다.
    if len(merged) > 1:
        tail = _TRAILING.sub("", _QUANTIFIER.sub(" ", merged[-1])).strip()
        if not _DOC_TAIL.search(tail):
            last = merged.pop()
            merged[-1] = f"{merged[-1]} {last}"

    return merged


# "면세사업자 : 부가가치세 면세사업자 수입금액 증명원" 처럼 앞에 조건 라벨이 붙는다.
# 콜론 뒤가 진짜 서류명이다.
_LABEL_PREFIX = re.compile(r"^[^:：]{1,15}[:：]\s*")


def _clean(piece: str) -> str:
    """수식어·글머리·괄호를 걷어낸다."""
    name = _LEADING_NOISE.sub("", piece)
    name = _LABEL_PREFIX.sub("", name)
    name = _OR_CLAUSE.sub("", name)
    name = _PAREN.sub("", name)
    # 빈 괄호 "( )" 는 앞에 글자가 없어 _PAREN이 못 지운다. 여기서 정리한다.
    name = re.sub(r"\(\s*\)", " ", name)
    name = _QUANTIFIER.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    name = _TRAILING.sub("", name).strip()
    return name


def _is_document_name(name: str) -> bool:
    """서류명인가. 카테고리·문장·잘린 문자열을 걸러낸다."""
    if not name:
        return False
    if len(name) < _MIN_NAME_LEN or len(name) > _MAX_NAME_LEN:
        return False
    if name in _PLACEHOLDERS or name.replace(" ", "") in _PLACEHOLDERS:
        return False
    # 서류명이라면 증/서/원/표/장 같은 글자로 끝난다.
    if not _DOC_TAIL.search(name):
        return False
    # 잘린 문장 조각 ("※ 면세사업자는 사업장현황신고 기한(2/")
    if any(ch in name for ch in "※→"):
        return False
    return True


def canonical_key(name: str) -> str:
    """정규화된 이름을 매핑 키로 바꾼다(공백 무시)."""
    return _CANONICAL.get(name.replace(" ", ""), _CANONICAL.get(name, name))


def find_canonical_names_in_text(
    text: str,
    *,
    allowed_names: Collection[str] | None = None,
) -> list[str]:
    """자연어 문장 안에 포함된 알려진 서류명을 표준명으로 반환한다.

    ``canonicalize``는 공고에서 추출한 서류명 한 항목을 정리하는 함수라서
    ``사업계획서에 대해 설명해줘`` 같은 질문 전체를 넣으면 문장으로 판단해
    버린다. 채팅에서는 문장 안의 별칭을 먼저 찾은 뒤 같은 표준명으로 모아야 한다.

    ``동의서``처럼 너무 짧고 범용적인 별칭은 오탐을 만들 수 있으므로, 짧은
    이름은 그 자체가 표준명일 때만 허용한다.
    """
    normalized_text = _match_key(text)
    if not normalized_text:
        return []

    allowed = set(allowed_names) if allowed_names is not None else None
    matches: list[tuple[int, int, str]] = []
    for alias, canonical in _CANONICAL.items():
        if allowed is not None and canonical not in allowed:
            continue

        alias_key = _match_key(alias)
        canonical_key_value = _match_key(canonical)
        if not alias_key:
            continue
        if len(alias_key) < 4 and alias_key != canonical_key_value:
            continue

        start = normalized_text.find(alias_key)
        if start >= 0:
            matches.append((start, -len(alias_key), canonical))

    matches.sort()
    result: list[str] = []
    seen: set[str] = set()
    for _start, _negative_length, canonical in matches:
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


def _match_key(value: str) -> str:
    """띄어쓰기와 구두점 차이를 무시하는 서류명 검색 키."""
    return re.sub(r"[^0-9a-z가-힣]", "", (value or "").lower())
