from __future__ import annotations

import re
from typing import Any

from app.services.normalization.common import _clean_text, _merge_unique_lists


def _extract_employee_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    patterns = [
        r"((?:상시\s*)?근로자\s*수?[^0-9]{0,12}(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과))",
        r"((\d+)\s*(?:명|인)\s*(미만|이하|이상|초과)[^.\n]{0,20}(?:근로자|사업장|업체))",
        r"((?:[가-힣A-Za-z0-9·ㆍ/&()\-]+업)[^0-9]{0,10}(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        operator, source_text = _operator_and_source_for_limit(text_value, match, match.group(3))
        return {
            "value": int(match.group(2)),
            "operator": operator,
            "unit": "people",
            "source_text": source_text,
            "extraction_method": "rule",
        }
    return None


def _extract_sales_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None

    # ``1억 4백만원``처럼 억 단위와 하위 단위가 섞인 금액은 기존의
    # 단일 숫자+단위 정규식으로는 1억원으로 잘려 저장된다.
    mixed_pattern = re.compile(
        r"((?:연\s*)?(?:전년도\s*)?(?:매출액?|연매출)[^0-9]{0,25}"
        r"(\d+(?:,\d{3})*)\s*억\s*"
        r"(?:(\d+(?:,\d{3})*)\s*(천만|백만|만)\s*원?)?"
        r"\s*(미만|이하|이상|초과)?)"
    )
    mixed_match = mixed_pattern.search(text_value)
    if mixed_match and mixed_match.group(3) and mixed_match.group(4):
        amount = int(mixed_match.group(2).replace(",", "")) * 100_000_000
        subunit_multiplier = {
            "천만": 10_000_000,
            "백만": 1_000_000,
            "만": 10_000,
        }[mixed_match.group(4)]
        amount += int(mixed_match.group(3).replace(",", "")) * subunit_multiplier
        operator, source_text = _operator_and_source_for_limit(
            text_value,
            mixed_match,
            mixed_match.group(5) or "이하",
        )
        return {
            "amount_krw": amount,
            "operator": operator,
            "source_text": source_text,
            "extraction_method": "rule",
        }

    pattern = re.compile(
        r"((?:연\s*)?(?:전년도\s*)?(?:매출액?|연매출)[^0-9]{0,25}"
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
        r"\s*(미만|이하|이상|초과)?)"
    )
    match = pattern.search(text_value)
    if not match:
        return None
    operator, source_text = _operator_and_source_for_limit(text_value, match, match.group(4) or "이하")
    return {
        "amount_krw": _money_to_krw(match.group(2), match.group(3)),
        "operator": operator,
        "source_text": source_text,
        "extraction_method": "rule",
    }


def _extract_business_age_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    patterns = [
        r"((?:창업|업력|영업기간|운영기간|영업개시|설립|개업일|등록일)[^0-9]{0,12}"
        r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과))",
        r"((?:사업자\s*등록(?:일)?|사업\s*개시일?|사업개시일)"
        r"(?:\s*(?:후|부터|로부터|기준|경과))?[^0-9]{0,12}"
        r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과))",
        r"((\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과)[^.\n]{0,20}(?:창업|업력|사업자\s*등록|사업\s*개시))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        limit_years = int(match.group(2))
        op_text = match.group(3)
        operator, source_text = _operator_and_source_for_limit(text_value, match, op_text)
        return {
            "value": limit_years,
            "operator": operator,
            "unit": "years",
            "source_text": source_text,
            "extraction_method": "rule",
        }
    return None


def _extract_money_conditions(value: str | None) -> list[dict[str, Any]]:
    text_value = _clean_text(value)
    if not text_value:
        return []
    pattern = re.compile(
        r"(.{0,24}?)(\d+(?:,\d{3})*(?:\.\d+)?)\s*"
        r"(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
        r"\s*(미만|이하|이상|초과|한도|내외|까지)?"
    )
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in pattern.finditer(text_value):
        context = _clean_text(match.group(1)) or ""
        source_text = _clean_text("".join(part or "" for part in match.groups())) or ""
        if source_text in seen:
            continue
        seen.add(source_text)
        values.append(
            {
                "kind": _money_condition_kind(context),
                "amount_krw": _money_to_krw(match.group(2), match.group(3)),
                "operator": _operator_symbol(match.group(4) or "이하"),
                "source_text": source_text,
            }
        )
        if len(values) >= 10:
            break
    return values


def _extract_application_methods(value: str | None) -> list[str]:
    text_value = _clean_text(value) or ""
    method_map = {
        "online": ("온라인", "홈페이지", "사이트", "전자신청", "인터넷", "플랫폼", "앱"),
        "visit": ("방문", "내방", "현장"),
        "mail": ("우편", "등기"),
        "fax": ("팩스", "FAX", "fax"),
        "email": ("이메일", "메일", "전자우편"),
        "e_document": ("전자문서", "공문", "온나라"),
    }
    return [method for method, tokens in method_map.items() if any(token in text_value for token in tokens)]


def _extract_contacts(value: str | None) -> list[str]:
    text_value = _clean_text(value) or ""
    contacts = re.findall(r"\b\d{2,4}-\d{3,4}-\d{4}\b|\b1[3568]\d{2}-\d{4}\b|\b1357\b", text_value)
    return _merge_unique_lists([], contacts)


def _tags_from_keyword_map(value: str | None, keyword_map: dict[str, tuple[str, ...]]) -> list[str]:
    text_value = _clean_text(value) or ""
    return [tag for tag, keywords in keyword_map.items() if any(keyword in text_value for keyword in keywords)]


def _extract_industry_condition(
    value: str | None,
    keyword_map: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    """Extract industries only when the surrounding sentence expresses a condition.

    A bare word such as ``디지털`` usually describes the support program, not the
    applicant's industry.  The result therefore keeps inclusion and exclusion
    evidence separately instead of exposing every keyword as a recommendation
    filter.
    """
    text_value = _clean_text(value) or ""
    if not text_value:
        return _empty_industry_condition()

    unrestricted_match = re.search(
        r"(?:업종\s*(?:제한|구분)\s*(?:없음|무)|업종\s*무관|전\s*업종|모든\s*업종)",
        text_value,
    )
    if unrestricted_match:
        return {
            "mode": "unrestricted",
            "include_tags": [],
            "exclude_tags": [],
            "confidence": 0.98,
            "extraction_method": "context_rule",
            "evidence": [
                {
                    "disposition": "unrestricted",
                    "source_text": unrestricted_match.group(0),
                }
            ],
        }

    include_tags: list[str] = []
    exclude_tags: list[str] = []
    evidence: list[dict[str, Any]] = []
    sentences = [
        sentence
        for sentence in (_clean_text(item) for item in re.split(r"[\n\r.;。]+", text_value))
        if sentence
    ]
    for sentence in sentences:
        exclusion = bool(
            re.search(
                r"(?:제외\s*업종|지원\s*(?:제외|불가)|신청\s*불가|대상에서\s*제외|업종\s*제외|제외)",
                sentence,
            )
        )
        for tag, keywords in keyword_map.items():
            for keyword in keywords:
                match = re.search(re.escape(keyword), sentence, re.IGNORECASE)
                if match is None:
                    continue
                window = sentence[max(0, match.start() - 35):match.end() + 35]
                if not _has_industry_condition_context(keyword, window, sentence):
                    continue
                disposition = "exclude" if exclusion else "include"
                target = exclude_tags if exclusion else include_tags
                if tag not in target:
                    target.append(tag)
                    evidence.append(
                        {
                            "tag": tag,
                            "keyword": keyword,
                            "disposition": disposition,
                            "source_text": sentence[:240],
                        }
                    )
                break

    if not include_tags and not exclude_tags:
        return _empty_industry_condition()
    return {
        "mode": "restricted",
        "include_tags": include_tags,
        "exclude_tags": exclude_tags,
        "confidence": 0.9,
        "extraction_method": "context_rule",
        "evidence": evidence,
    }


def _has_industry_condition_context(keyword: str, window: str, sentence: str) -> bool:
    if re.search(
        r"(?:업종|업체|기업|사업자|사업체|산업|영위|종사|운영|경영|소공인|상인|점포)",
        window,
    ):
        return True
    if re.search(rf"{re.escape(keyword)}\s*업", window, re.IGNORECASE):
        return True
    if keyword.endswith("업") and re.search(
        rf"{re.escape(keyword)}\s*(?:인|체|자)",
        window,
        re.IGNORECASE,
    ):
        return True
    business_noun = keyword.endswith(
        ("업", "점", "식당", "카페", "베이커리", "공장", "호텔", "상점", "가맹점", "시장")
    )
    return business_noun and bool(re.search(r"(?:지원\s*대상|신청\s*대상|대상)", sentence))


def _empty_industry_condition() -> dict[str, Any]:
    return {
        "mode": "unknown",
        "include_tags": [],
        "exclude_tags": [],
        "confidence": 0.2,
        "extraction_method": "context_rule",
        "evidence": [],
    }


def _operator_symbol(value: str) -> str:
    return {
        "미만": "<",
        "이하": "<=",
        "초과": ">",
        "이상": ">=",
        "경과": ">=",
        "한도": "<=",
        "까지": "<=",
        "내외": "~",
    }.get(value, "<=")


def _direct_exclusion_match(tail: str) -> re.Match[str] | None:
    return re.search(
        r"^\s*(?:인\s*)?(?:업소|업체|기업|사업체|대상자)?\s*"
        r"(?:은|는|을|를)?\s*(?:지원\s*대상에서\s*)?"
        r"(?:제외|지원\s*불가)(?!\s*업종)",
        tail,
    )


def _operator_and_source_for_limit(text_value: str, match: re.Match[str], operator_text: str) -> tuple[str, str]:
    operator = _operator_symbol(operator_text)
    tail = text_value[match.end():match.end() + 40]
    exclusion_match = _direct_exclusion_match(tail)
    source_text = match.group(1)
    if exclusion_match:
        operator = {">=": "<", ">": "<=", "<=": ">", "<": ">="}.get(operator, operator)
        source_text = _clean_text(f"{source_text}{exclusion_match.group(0)}") or source_text
    return operator, source_text


def _money_to_krw(number_text: str, unit: str) -> int:
    number = float(number_text.replace(",", ""))
    compact_unit = re.sub(r"\s+", "", unit)
    if compact_unit == "억원":
        multiplier = 100_000_000
    elif compact_unit == "천만원":
        multiplier = 10_000_000
    elif compact_unit == "백만원":
        multiplier = 1_000_000
    elif compact_unit == "만원":
        multiplier = 10_000
    else:
        multiplier = 1
    return int(number * multiplier)


def _money_condition_kind(context: str) -> str:
    if "매출" in context:
        return "sales"
    if "보수" in context or "소득" in context:
        return "income"
    if "지원" in context or "한도" in context or "자금" in context:
        return "support_amount"
    if "부담" in context:
        return "self_payment"
    return "amount"
