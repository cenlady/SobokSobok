from __future__ import annotations

import html
import re
from typing import Any

from app.models.gov24 import Gov24ServiceDetail
from app.services.normalization.common import _clean_text, _join_text

SECTION_TYPE_BY_TITLE = {
    "사업목적": "summary",
    "서비스 목적": "summary",
    "지원규모": "support_content",
    "지원내용": "support_content",
    "지원 내용": "support_content",
    "지원대상": "eligibility",
    "지원 대상": "eligibility",
    "이용대상": "eligibility",
    "이용 대상": "eligibility",
    "신청대상": "eligibility",
    "신청 대상": "eligibility",
    "지원자격": "eligibility",
    "지원 자격": "eligibility",
    "자격요건": "eligibility",
    "자격 요건": "eligibility",
    "가입대상": "eligibility",
    "가입 대상": "eligibility",
    "가입기준": "eligibility",
    "가입 기준": "eligibility",
    "가입요건": "eligibility",
    "가입 요건": "eligibility",
    "대상자": "eligibility",
    "대상자 기준": "eligibility",
    "제한기준": "restriction",
    "제한 기준": "restriction",
    "지원제외": "restriction",
    "지원 제외": "restriction",
    "제외대상": "restriction",
    "제외 대상": "restriction",
    "이용용도": "purpose",
    "이용 용도": "purpose",
    "이용료": "cost",
    "이용 료": "cost",
    "선정기준": "eligibility",
    "선정 기준": "eligibility",
    "대상": "eligibility",
    "신청기간": "application",
    "신청 기간": "application",
    "신청기한": "deadline",
    "신청 기한": "deadline",
    "신청방법": "application",
    "신청 방법": "application",
    "신청·접수": "application",
    "신청‧접수": "application",
    "접수방법": "application",
    "접수 방법": "application",
    "지원절차": "procedure",
    "지원 절차": "procedure",
    "추진절차": "procedure",
    "추진 절차": "procedure",
    "구비서류": "requirements",
    "구비 서류": "requirements",
    "신청서류": "requirements",
    "신청 서류": "requirements",
    "제출서류": "requirements",
    "제출 서류": "requirements",
    "제출자료": "requirements",
    "제출 자료": "requirements",
    "제출서류 및 신청양식": "requirements",
    "제출서류 안내": "requirements",
    "제출서류 양식": "requirements",
    "증빙서류": "requirements",
    "증빙 서류": "requirements",
    "필요서류": "requirements",
    "필요 서류": "requirements",
    "문의처": "contact",
    "전화문의": "contact",
    "접수기관": "application",
    "사업명": "summary",
}

SECTION_TITLE_ALIASES = {
    "신청ㆍ접수": "신청·접수",
    "신청·접수": "신청·접수",
    "신청‧접수": "신청·접수",
    "신청 접수": "신청·접수",
    "자세한 사항은 여기로 문의하세요": "문의처",
    "자세한 사항은 여기로 문의하시기 바랍니다": "문의처",
    "자세한 사항은 아래 문의처로 연락바랍니다": "문의처",
}

_DOCUMENT_NAME_TOKENS = (
    "신청서",
    "동의서",
    "확인서",
    "증명",
    "증명서",
    "증명원",
    "등록증",
    "계획서",
    "신고서",
    "명세서",
    "서약서",
    "계약서",
    "허가증",
    "면허증",
    "견적서",
    "추천서",
    "보고서",
    "수료증",
    "자격증",
    "영수증",
    "내역서",
    "명부",
    "사진",
    "등본",
    "초본",
    "사본",
    "통장",
    "재무제표",
    "결산서",
    "이력서",
    "체크리스트",
    "원천징수",
    "납세증명",
    "소득금액증명",
    "인감증명",
    "가족관계증명",
    "재직증명",
    "경력증명",
    "사업자등록",
    "건강보험",
    "부가가치세",
    "매출자료",
    "증빙자료",
)

_REQUIREMENT_HEADING_RE = re.compile(
    r"^(?:(?:제출|구비|신청|필수|증빙|필요|첨부|준비)\s*(?:서류|자료|양식)|"
    r"신청\s*시\s*제출(?:할|하는)?\s*(?:서류|자료|양식))"
    r"(?:\s*(?:목록|안내))?\s*[:：]?\s*(.*)$"
)

_SECTION_HEADING_RE = re.compile(
    r"^(?:지원\s*(?:대상|내용|규모|제외)|신청\s*(?:대상|방법|기간|기한)|"
    r"접수\s*(?:방법|기간)|선정\s*(?:기준|방법)|평가\s*(?:기준|방법)|"
    r"문의처|추진\s*절차|사업\s*(?:목적|개요|내용)|유의\s*사항|참고\s*사항|"
    r"제외\s*대상|제한\s*기준)\s*[:：]?$"
)


def _normalize_section_title(value: str | None) -> str | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    text_value = text_value.strip("[](){}<>:：※ㆍ·•- ")
    text_value = re.sub(r"\s+", " ", text_value)
    return SECTION_TITLE_ALIASES.get(text_value, text_value)


def _document_type_for_title(value: str | None) -> str:
    title = _normalize_section_title(value)
    if not title:
        return "section"
    compact_title = re.sub(r"\s+", "", title)
    for key, document_type in SECTION_TYPE_BY_TITLE.items():
        if re.sub(r"\s+", "", key) in compact_title:
            return document_type
    if "서류" in compact_title:
        return "requirements"
    if "문의" in compact_title or "연락" in compact_title:
        return "contact"
    if "신청" in compact_title or "접수" in compact_title:
        return "application"
    if "대상" in compact_title or "자격" in compact_title or "조건" in compact_title:
        return "eligibility"
    if "내용" in compact_title or "규모" in compact_title:
        return "support_content"
    return "section"


def _first_section_text_by_type(
    sections: list[dict[str, str | None]],
    document_type: str,
) -> str | None:
    values = [
        section.get("text")
        for section in sections
        if (section.get("document_type") or _document_type_for_title(section.get("title"))) == document_type
    ]
    return _join_text(values)


def _extract_required_documents(
    sections: list[dict[str, str | None]],
    source: str,
) -> list[dict[str, Any]]:
    candidate_texts = [
        section.get("text")
        for section in sections
        if (section.get("document_type") or _document_type_for_title(section.get("title"))) == "requirements"
    ]

    values: list[dict[str, Any]] = []
    for candidate in candidate_texts:
        values.extend(
            _document_items_from_text(
                candidate,
                source=source,
                confidence=0.75,
                extraction_method="requirement_section_rule",
            )
        )
    return _dedupe_document_items(values)


def _extract_required_documents_from_attachment(
    value: str | None,
    source: str,
) -> list[dict[str, Any]]:
    """Extract only from explicit requirement sections in an attachment.

    Attachment text often contains a whole HTML table or announcement body.  Scanning
    that entire text turns ordinary prose into fake document names, so a heading is a
    required boundary here.
    """
    values: list[dict[str, Any]] = []
    for requirement_text in _requirement_sections_from_attachment(value):
        if _is_internal_requirement_section(requirement_text):
            continue
        values.extend(
            _document_items_from_text(
                requirement_text,
                source=source,
                confidence=0.85,
                extraction_method="attachment_requirement_section",
            )
        )

    return _dedupe_document_items(values)


def _extract_required_document_llm_candidates(
    sections: list[dict[str, str | None]],
    attachment_texts: list[str] | None = None,
) -> list[dict[str, str]]:
    """Return grounded, unresolved names from explicit requirement sections."""
    candidate_texts = [
        section.get("text")
        for section in sections
        if (section.get("document_type") or _document_type_for_title(section.get("title"))) == "requirements"
    ]
    for attachment_text in attachment_texts or []:
        candidate_texts.extend(
            section
            for section in _requirement_sections_from_attachment(attachment_text)
            if not _is_internal_requirement_section(section)
        )

    values: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate_text in candidate_texts:
        context = _clean_text(_strip_markup(candidate_text))
        if not context:
            continue
        for line in _split_requirement_lines(candidate_text):
            for raw_name in _split_document_names(line):
                name = _normalize_document_name(raw_name)
                if not name or not _is_weak_document_name(name):
                    continue
                if not _is_safe_llm_document_candidate(name):
                    continue
                key = _document_name_key(name)
                if not key or key in seen:
                    continue
                seen.add(key)
                values.append({"name": name, "context": context})
    return values


def _requirement_sections_from_attachment(value: str | None) -> list[str]:
    lines = _plain_text_lines(value)
    if not lines:
        return []

    sections: list[str] = []
    index = 0
    while index < len(lines):
        match = _REQUIREMENT_HEADING_RE.match(lines[index])
        if match is None:
            index += 1
            continue

        section_lines: list[str] = []
        inline_text = _clean_text(match.group(1))
        if inline_text:
            section_lines.append(inline_text)

        index += 1
        while index < len(lines) and len(section_lines) < 25:
            line = lines[index]
            if _REQUIREMENT_HEADING_RE.match(line) or (
                len(line) <= 45 and _SECTION_HEADING_RE.match(line)
            ):
                break
            section_lines.append(line)
            index += 1

        section_text = "\n".join(section_lines)
        if section_text:
            sections.append(section_text)
    return sections


def _document_items_from_text(
    value: str | None,
    *,
    source: str,
    confidence: float,
    extraction_method: str,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line in _split_requirement_lines(value):
        for raw_name in _split_document_names(line):
            name = _normalize_document_name(raw_name)
            if not name or _is_weak_document_name(name):
                continue
            values.append(
                {
                    "name": name,
                    "description": "",
                    "source": source,
                    "confidence": confidence,
                    "extraction_method": extraction_method,
                }
            )
    return values


_INTERNAL_REQUIREMENT_MARKERS = (
    "사업비",
    "교육기관",
    "e나라도움",
    "정산",
    "강사비",
    "상담비",
    "실습재료비",
    "임차사용료",
    "수행보고서",
    "집행증빙",
    "참여인력",
)


def _is_internal_requirement_section(value: str | None) -> bool:
    """Reject operational/settlement sections from applicant requirements."""
    lines = _plain_text_lines(value)
    if not lines:
        return False
    # A requirement section can bleed into a later appendix or sanctions table.
    # Only the opening context decides whether the section belongs to operations.
    opening = "\n".join(lines[:12])
    return any(marker in opening for marker in _INTERNAL_REQUIREMENT_MARKERS)


def _split_document_names(value: str) -> list[str]:
    text_value = _clean_text(value)
    if not text_value:
        return []
    # 가운데점(·/ㆍ)은 ``개인정보 수집·이용 동의서``처럼 문서명 내부에도
    # 자주 쓰이므로 목록 구분자로 취급하지 않는다.
    parts = re.split(r"\s*(?:,|，|\+|•)\s*", text_value)
    values: list[str] = []
    for part in (cleaned for item in parts if (cleaned := _clean_text(item))):
        alternatives = re.split(r"\s+(?:및|또는)\s+", part)
        if len(alternatives) > 1 and all(_contains_document_token(item) for item in alternatives):
            values.extend(alternatives)
        else:
            values.append(part)
    return values


def _contains_document_token(value: str) -> bool:
    return any(token in value for token in _DOCUMENT_NAME_TOKENS)


def _normalize_document_name(value: str | None) -> str | None:
    text_value = _clean_text(_strip_markup(value))
    if not text_value:
        return None
    text_value = text_value.lstrip("# ")
    text_value = re.sub(
        r"^\[?(?:서식|별지|붙임|별첨)\s*\d+[^]]*\]?\s*",
        "",
        text_value,
    )
    text_value = re.sub(r"^(?:유효기간\s*내|최근\s*\d+개월\s*이내\s*발급(?:분)?)\s*", "", text_value)
    text_value = re.sub(r"^\(?최근\s*\d+개월\s*이내\)?\s*", "", text_value)
    text_value = re.sub(r"^(?:또는|및)\s*", "", text_value)
    text_value = re.sub(
        r"^(?:[-–—*※○◦▪▶►‣❍□]+|[①-⑳]+|\(\d{1,2}\)|\d{1,2}[.)]|[가-하][.)])\s*",
        "",
        text_value,
    )
    text_value = re.sub(
        r"^(?:(?:필수|선택|공통|해당자|개인|법인|신청자)\s*){1,2}[:：-]\s*",
        "",
        text_value,
    )
    if ":" in text_value or "：" in text_value:
        name_part = re.split(r"[:：]", text_value, maxsplit=1)[0]
        if any(token in name_part for token in _DOCUMENT_NAME_TOKENS):
            text_value = name_part
    text_value = re.sub(r"^.*?인\s*경우(?:에는?)?\s*", "", text_value)
    text_value = re.sub(r"^(?:이\s*)?경우\s*", "", text_value)
    text_value = re.sub(
        r"\s+(?:공공\s*)?마이데이터\s+(?:수신|조회)\s*(?:불가|불가능).*$",
        "",
        text_value,
    )
    text_value = re.sub(r"\s+(?:제출|필요|제출\s*필수)$", "", text_value)
    text_value = re.sub(r"\s+등\s*(?:필요|제출)?$", "", text_value)
    text_value = re.sub(r"\s+등\s+\d{4}년.*$", "", text_value)
    return _clean_text(text_value.strip("[]{}<>|:：- "))


def _is_weak_document_name(value: str) -> bool:
    return _is_unsafe_document_name(value) or not _contains_document_token(value)


def _is_safe_llm_document_candidate(value: str) -> bool:
    text_value = _clean_text(value) or ""
    if _is_unsafe_document_name(text_value) or len(text_value) > 70:
        return False
    if len(text_value.split()) > 12:
        return False
    if re.search(r"(?:해야|하여|하고|바라|가능|필요|경우|대상|확인)$", text_value):
        return False
    return bool(re.search(r"[가-힣A-Za-z0-9]", text_value)) and _looks_like_document_noun(
        text_value
    )


def _looks_like_document_noun(value: str) -> bool:
    text_value = re.sub(r"\s*\([^)]{0,30}\)\s*$", "", value).strip()
    if text_value.endswith(("세무서", "지원센터", "센터장", "에서")):
        return False
    document_suffixes = (
        "서",
        "증",
        "증빙",
        "명부",
        "대장",
        "내역",
        "사진",
        "도면",
        "원본",
        "포트폴리오",
        "카탈로그",
        "브로슈어",
        "캡처본",
        "캡쳐본",
        "동의",
    )
    return text_value.endswith(document_suffixes)


def _is_unsafe_document_name(value: str) -> bool:
    text_value = _clean_text(value) or ""
    if len(text_value) < 2 or len(text_value) > 90:
        return True
    if text_value.count("(") != text_value.count(")"):
        return True
    if re.search(r"<[^>]*>|(?:th|td|tr)>|https?://|www\.", text_value, re.IGNORECASE):
        return True
    # 공공 마이데이터의 표준재무제표증명 응답 필드가 표에서 분리되면
    # ``증명내용 표준대차대조표...`` 같은 문자열이 제출서류명처럼 보인다.
    # 이 값들은 신청자가 제출하는 문서가 아니라 API 응답의 세부 필드명이다.
    if text_value.startswith(("증명내용", "부속명세서")):
        return True
    if re.search(
        r"(?:표준대차대조표|표준손익계산서|표준원가명세서|"
        r"제조원가명세서|공사원가명세서|임대원가명세서|분양원가명세서|"
        r"운송원가명세서|기타원가명세서).*(?:좌|우|개인\s*[12]|법인)",
        text_value,
    ):
        return True
    if re.search(
        r"(?:영위하는|작성하여|제출하여|확인할\s*수|판정기준표|"
            r"중위소득|본인부담금|건강보험료\s*납부\s*기준)",
        text_value,
    ):
        return True
    if re.search(r"(?:사장님\s*)?(?:영상|동영상)\s*설명서", text_value):
        return True
    if re.search(r"수료증.*(?:발급\s*대상|출력|명의)", text_value):
        return True
    if "판정기준표" in text_value or "중위소득" in text_value:
        return True
    weak_tokens = (
        "자세한",
        "첨부파일",
        "공고문",
        "참고",
        "세부내용",
        "문의처",
        "홈페이지",
        "담당자",
        "제출서류와 함께",
        "제출서류 양식",
        "신청서류 검토",
        "소상공인24 통해",
        "온라인 접수",
        "해당없음",
        "해당 없음",
        "없음",
        "사업별 공고",
        "제출서류 안내",
        "제출 서류 안내",
        "제출서류 목록",
        "제출 서류 목록",
        "제출서류 리스트",
        "제출 서류 리스트",
        "제출서류 확인",
        "제출 서류 확인",
        "아래 서류",
        "다음 서류",
        "관련 서류",
        "기타 서류",
        "증빙 서류 일체",
        "제출하여",
        "제출해야",
        "제출 바랍니다",
        "제출하시",
        "첨부하시",
        "작성 후",
        "발급받아",
        "서류 중",
        "증빙서류 중",
        "택1",
        "택 1",
        "미제출",
        "수정사항",
        "이사장",
        "서류에 명시",
        "공통서류 제출",
        "공통 서류 제출",
        "폐업하지 않은",
        "신청 시 제출",
        "제출할 자료",
    )
    if any(token in text_value for token in weak_tokens):
        return True
    if text_value in {"서류", "자료", "제출자료", "신청서류", "구비서류", "증빙서류"}:
        return True
    if text_value == "사업자등록번호" or text_value.endswith("확인서류"):
        return True
    if re.search(r"(?:가능|인정|적합|명시)[.!?]?$", text_value):
        return True
    if re.search(r"(?:합니다|됩니다|있습니다|바랍니다|하세요|십시오)[.!?]?$", text_value):
        return True
    return False


def _split_requirement_lines(value: str | None) -> list[str]:
    plain_text = _strip_markup(value)
    if not plain_text:
        return []
    lines = re.split(
        r"(?:\n+|○|ㆍ|•|◦|▪|▶|[-–]\s+|\(\s*[0-9ivxIVXⅰ-ⅹ]+\s*\)|\d+[.)])",
        plain_text,
    )
    return [
        cleaned
        for line in lines
        if (cleaned := _clean_text(line))
    ]


def _strip_markup(value: str | None) -> str:
    if value is None:
        return ""
    text_value = html.unescape(str(value))
    text_value = re.sub(
        r"<\s*(?:script|style)\b[^>]*>.*?<\s*/\s*(?:script|style)\s*>",
        " ",
        text_value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text_value = re.sub(
        r"<\s*(?:br|/p|/div|/li|/tr|/table|/h[1-6])\s*/?\s*>",
        "\n",
        text_value,
        flags=re.IGNORECASE,
    )
    text_value = re.sub(
        r"<\s*/?\s*(?:td|th)\b[^>]*>",
        "\n",
        text_value,
        flags=re.IGNORECASE,
    )
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    text_value = re.sub(r"\r\n?", "\n", text_value)
    text_value = re.sub(r"[ \t\f\v]+", " ", text_value)
    text_value = re.sub(r" *\n *", "\n", text_value)
    return text_value.strip()


def _plain_text_lines(value: str | None) -> list[str]:
    return [
        cleaned
        for line in _strip_markup(value).splitlines()
        if (cleaned := _clean_text(line))
    ]


def _required_documents_from_gov24(detail: Gov24ServiceDetail | None) -> list[dict[str, Any]]:
    if detail is None:
        return []
    values = []
    for source, text_value in (
        ("required_docs", _gov24_applicant_required_text(detail.required_docs)),
        ("required_docs_by_official", detail.required_docs_by_official),
        ("identity_required_docs", detail.identity_required_docs),
    ):
        values.extend(
            _document_items_from_text(
                text_value,
                source=source,
                confidence=0.95,
                extraction_method="gov24_detail",
            )
        )
    return _dedupe_document_items(values)


def _gov24_applicant_required_text(value: str | None) -> str | None:
    """Keep Gov24 applicant-upload sections, excluding staff-verifiable fields."""
    lines = _plain_text_lines(value)
    if not lines:
        return value

    kept: list[str] = []
    skip_section = False
    for line in lines:
        compact = re.sub(r"\s+", "", line)
        is_section_heading = line.lstrip().startswith(("○", "ㅇ", "◦"))
        if "직원확인가능서류" in compact or "신청인미제출서류" in compact:
            skip_section = True
            continue
        if skip_section and is_section_heading:
            skip_section = False
        if not skip_section:
            kept.append(line)
    return "\n".join(kept)


def _dedupe_document_items(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        key = _document_name_key(item.get("name"))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _document_name_key(value: str | None) -> str:
    text_value = (_clean_text(value) or "").replace("・", "·").replace("ㆍ", "·")
    if not text_value:
        return ""
    # 같은 제출물을 발급 시점·원본/사본·수량·별지 표기만 달리해 반복하는
    # 공고가 많다. 표시명은 보존하되 dedupe key에서만 이런 부가 표기를 제거한다.
    text_value = re.sub(r"\[?별지\s*\d+[^\]]*\]?", "", text_value)
    text_value = re.sub(
        r"\([^)]*(?:사본|원본|공고일|신청일|발급|유효|이내|기간|\d+\s*시간\s*이상)[^)]*\)",
        "",
        text_value,
    )
    text_value = re.sub(r"(?:각\s*)?\d+\s*부\b", "", text_value)
    text_value = text_value.replace("(내역)", "")
    text_value = text_value.replace("부과현황", "부과내역")
    text_value = text_value.replace("부과내역내역", "부과내역")
    text_value = re.sub(r"(?:8개\s*은행권|은행\s*발급)", "", text_value)
    text_value = text_value.replace("증명원", "증명")
    text_value = re.sub(r"[^0-9A-Za-z가-힣]", "", text_value)
    return text_value.lower()
