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
    r"^(?:제출|구비|신청|필수|증빙|필요|첨부)\s*(?:서류|자료|양식)"
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
    lines = _plain_text_lines(value)
    if not lines:
        return []

    values: list[dict[str, Any]] = []
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

        values.extend(
            _document_items_from_text(
                "\n".join(section_lines),
                source=source,
                confidence=0.85,
                extraction_method="attachment_requirement_section",
            )
        )

    return _dedupe_document_items(values)


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
    text_value = re.sub(r"^\[(?:서식|별지|붙임)\s*\d+[^]]*]\s*", "", text_value)
    text_value = re.sub(r"^(?:유효기간\s*내|최근\s*\d+개월\s*이내\s*발급(?:분)?)\s*", "", text_value)
    text_value = re.sub(
        r"^(?:[-–—*※○◦▪▶]+|[①-⑳]+|\(\d{1,2}\)|\d{1,2}[.)]|[가-하][.)])\s*",
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
    text_value = re.sub(r"\s+(?:제출|필요|제출\s*필수)$", "", text_value)
    text_value = re.sub(r"\s+등\s*(?:필요|제출)?$", "", text_value)
    text_value = re.sub(r"\s+등\s+\d{4}년.*$", "", text_value)
    return _clean_text(text_value.strip("[]{}<>|:：- "))


def _is_weak_document_name(value: str) -> bool:
    text_value = _clean_text(value) or ""
    if len(text_value) < 2 or len(text_value) > 90:
        return True
    if text_value.count("(") != text_value.count(")"):
        return True
    if re.search(r"<[^>]*>|(?:th|td|tr)>|https?://|www\.", text_value, re.IGNORECASE):
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
    return not any(token in text_value for token in _DOCUMENT_NAME_TOKENS)


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
        ("required_docs", detail.required_docs),
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
    return re.sub(r"\s+", "", text_value).lower()
