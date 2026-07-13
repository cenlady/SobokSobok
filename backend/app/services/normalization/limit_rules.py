from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.services.normalization.common import _clean_text
from app.services.normalization.field_extractors import (
    _direct_exclusion_match,
    _extract_sales_limit,
    _money_to_krw,
    _operator_symbol,
)

LIMIT_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "employee_limit": {
        # 공고마다 같은 개념을 ``근로자``, ``종사자``, ``상시인원`` 등으로
        # 다르게 표현하므로 현재 수집된 업종명만 나열하지 않습니다.
        "keywords": (
            "근로자",
            "상시근로자수",
            "직원",
            "종업원",
            "종사자",
            "고용인원",
            "상시인원",
            "근로 인원",
            "근무자",
        ),
        # 업종별 인원 기준은 업종명이 새로 추가되어도 후보로 보냅니다.
        "anchor_pattern": r"[가-힣A-Za-z0-9·ㆍ/&()\-]+업",
        "numeric_unit_pattern": r"\d+(?:,\d{3})*\s*(?:명|인)(?=\s*(?:미만|이하|이상|초과|약|내외|규모|$))",
        "maximum": 1_000_000,
    },
    "sales_limit": {
        "keywords": ("매출", "매출액", "연매출"),
        "numeric_unit_pattern": (
            r"\d+(?:,\d{3})*(?:\.\d+)?\s*"
            r"(?:억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
            r"(?=\s*(?:미만|이하|이상|초과|약|내외|범위|$))"
        ),
        "maximum": 9_000_000_000_000_000_000,
    },
    "business_age_limit": {
        "keywords": (
            "업력",
            "창업",
            "사업개시",
            "사업 개시",
            "사업자등록",
            "사업자 등록",
            "개업",
            "영업기간",
            "운영기간",
            "영업개시",
            "설립",
            "개업일",
            "등록일",
        ),
        "numeric_unit_pattern": r"\d+\s*년(?=\s*(?:미만|이하|이상|초과|이내|약|내외|경과|$))",
        "maximum": 100,
    },
}


def _limit_candidate_context(value: str | None, field: str) -> str | None:
    text_value = _clean_text(value)
    spec = LIMIT_FIELD_SPECS.get(field)
    if not text_value or not spec:
        return None

    spans: list[tuple[int, int]] = []
    qualifier_pattern = re.compile(r"미만|이하|이상|초과|이내|경과|약|내외|범위")
    numeric_unit_pattern = re.compile(spec["numeric_unit_pattern"])
    for keyword in spec["keywords"]:
        for match in re.finditer(re.escape(keyword), text_value, re.IGNORECASE):
            start = max(match.start() - 60, 0)
            end = min(match.end() + 140, len(text_value))
            window = text_value[start:end]
            numeric_matches = list(numeric_unit_pattern.finditer(window))
            if not numeric_matches:
                continue
            if not qualifier_pattern.search(window):
                continue
            keyword_start = match.start() - start
            keyword_end = match.end() - start
            is_near_keyword = any(
                min(abs(number.start() - keyword_end), abs(keyword_start - number.end())) <= 60
                for number in numeric_matches
            )
            if not is_near_keyword:
                continue
            spans.append((start, end))

    # 일부 공고는 "상시근로자"라는 말을 생략하고
    # "도소매·서비스업(5인 미만), 제조·건설업(10인 미만)"처럼 쓴다.
    # 업종 앵커가 있는 경우에만 직원 수 후보로 추가한다.
    if field == "employee_limit" and spec.get("anchor_pattern"):
        for match in re.finditer(spec["anchor_pattern"], text_value):
            start = max(match.start() - 20, 0)
            end = min(match.end() + 80, len(text_value))
            window = text_value[start:end]
            numeric_matches = list(numeric_unit_pattern.finditer(window))
            if not numeric_matches or not qualifier_pattern.search(window):
                continue
            spans.append((start, end))

    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    windows = [text_value[start:end] for start, end in merged]
    return _clean_text(" ... ".join(windows))


def _limit_fields_requiring_llm(
    text_value: str | None,
    parsed_limits: dict[str, dict[str, Any] | None],
) -> list[str]:
    requested: list[str] = []
    for field in LIMIT_FIELD_SPECS:
        context = _limit_candidate_context(text_value, field)
        if not context:
            continue
        parsed = parsed_limits.get(field)
        numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", context)
        has_lower = bool(re.search(r"이상|초과", context))
        has_upper = bool(re.search(r"이하|미만|이내|경과하지", context))
        is_two_sided_range = len(numbers) >= 2 and has_lower and has_upper
        is_complex = bool(_complex_limit_payload(field, context))
        if parsed is None or is_two_sided_range or is_complex:
            requested.append(field)
    return requested


def _select_limit_context(text_value: str, requested_fields: list[str]) -> str:
    selected = [
        context
        for field in requested_fields
        if (context := _limit_candidate_context(text_value, field))
    ]
    context = _clean_text(" ... ".join(dict.fromkeys(selected))) or text_value
    return context[: settings.NORMALIZE_LLM_MAX_CONTEXT_CHARS]


def _coerce_limit_int(value: Any, maximum: int) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    elif isinstance(value, str):
        compact = value.replace(",", "").strip()
        if not re.fullmatch(r"\d+", compact):
            return None
        parsed = int(compact)
    else:
        return None
    return parsed if 0 <= parsed <= maximum else None


def _normalize_llm_operator(value: Any, side: str, evidence: str) -> str | None:
    aliases = {
        "이상": ">=",
        "초과": ">",
        "이하": "<=",
        "미만": "<",
        "이내": "<=",
    }
    operator = aliases.get(str(value).strip(), str(value).strip()) if value is not None else None
    allowed = {">=", ">"} if side == "min" else {"<=", "<"}
    if operator in allowed:
        return operator
    if side == "min":
        if "초과" in evidence:
            return ">"
        if "이상" in evidence or ("경과" in evidence and "경과하지" not in evidence):
            return ">="
    else:
        if "미만" in evidence:
            return "<"
        if any(token in evidence for token in ("이하", "이내", "경과하지")):
            return "<="
    return None


def _numeric_match_has_field_context(
    field: str,
    evidence: str,
    numeric_match: re.Match[str],
    *,
    max_distance: int = 60,
) -> bool:
    spec = LIMIT_FIELD_SPECS[field]
    separators = re.compile(r"[。.!?;]|(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨|○|◦|▪|▶|▷|▸)")
    for keyword in spec["keywords"]:
        for keyword_match in re.finditer(re.escape(keyword), evidence, re.IGNORECASE):
            distance = min(
                abs(numeric_match.start() - keyword_match.end()),
                abs(keyword_match.start() - numeric_match.end()),
            )
            if distance > max_distance:
                continue
            start = min(keyword_match.end(), numeric_match.end())
            end = max(keyword_match.start(), numeric_match.start())
            between = evidence[start:end]
            if separators.search(between):
                continue
            if field == "sales_limit" and re.search(
                r"임차료|지원금|지원액|보증한도|대출한도|융자한도|자금한도|사업비",
                between,
            ):
                continue
            if field == "sales_limit" and "억" in evidence[max(0, numeric_match.start() - 6):numeric_match.start()]:
                # ``1억 4백만원``의 4백만원만 별도 매출액으로 해석하지 않는다.
                continue
            return True
    return False
def _bounds_from_evidence(field: str, evidence: str) -> dict[str, Any]:
    bounds: dict[str, Any] = {
        "min_value": None,
        "min_operator": None,
        "max_value": None,
        "max_operator": None,
        "constraints": [],
        "has_alternatives": False,
    }
    if field == "employee_limit":
        matches = re.finditer(r"(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과)", evidence)
        extracted = [
            (int(match.group(1)), _operator_symbol(match.group(2)), match.group(0), match.end())
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]
    elif field == "sales_limit":
        matches = re.finditer(
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*"
            r"(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)\s*"
            r"(미만|이하|이상|초과)",
            evidence,
        )
        extracted = [
            (
                _money_to_krw(match.group(1), match.group(2)),
                _operator_symbol(match.group(3)),
                match.group(0),
                match.end(),
            )
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]
        direct_sales = _extract_sales_limit(evidence)
        if direct_sales and not any(
            item[0] == direct_sales["amount_krw"] and item[1] == direct_sales["operator"]
            for item in extracted
        ):
            extracted.insert(
                0,
                (
                    direct_sales["amount_krw"],
                    direct_sales["operator"],
                    direct_sales["source_text"],
                    -1,
                ),
            )
    else:
        matches = re.finditer(
            r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과)",
            evidence,
        )
        extracted = [
            (int(match.group(1)), _operator_symbol(match.group(2)), match.group(0), match.end())
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]

    side_values: dict[str, set[int]] = {"min": set(), "max": set()}
    seen_constraints: set[tuple[int, str, str]] = set()
    for value, operator, source_text, match_end in extracted:
        tail = evidence[match_end:match_end + 40] if match_end >= 0 else ""
        exclusion_match = _direct_exclusion_match(tail) if tail else None
        if exclusion_match:
            operator = {">=": "<", ">": "<=", "<=": ">", "<": ">="}.get(operator, operator)
            source_text = _clean_text(f"{source_text}{exclusion_match.group(0)}") or source_text
        side = "min" if operator in {">", ">="} else "max"
        side_values[side].add(value)
        bounds[f"{side}_value"] = value
        bounds[f"{side}_operator"] = operator
        marker = (value, operator, source_text)
        if marker in seen_constraints:
            continue
        seen_constraints.add(marker)
        bounds["constraints"].append(
            {"value": value, "operator": operator, "source_text": source_text}
        )
    min_value = bounds["min_value"]
    max_value = bounds["max_value"]
    bounds["has_alternatives"] = (
        len(bounds["constraints"]) > 2
        or any(len(values) > 1 for values in side_values.values())
        or (min_value is not None and max_value is not None and min_value > max_value)
    )
    return bounds


def _branching_limit_reason(context: str, field: str) -> str | None:
    """단일 숫자로 평탄화하면 의미가 바뀌는 분기/관계 조건을 찾습니다."""
    all_required = bool(re.search(r"(?:모두|전부|모든).{0,12}(?:충족|해당|요건)", context))
    branch_markers = (
        "각 호 중",
        "다음 각 호",
        "중 1개",
        "중 하나",
        "어느 하나",
        "자금별",
        "유형별",
        "업종별",
    )
    if any(marker in context for marker in branch_markers):
        return "branching_condition"
    if not all_required and re.search(r"(?:^|\s)(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨)", context) and len(
        re.findall(r"(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨)", context)
    ) >= 2:
        return "numbered_alternatives"
    if len(re.findall(r"(?:창업|경영개선|점포임차|대환|일반|우대)\s*자금\s*:", context)) >= 2:
        return "named_alternatives"
    if "또는" in context:
        return "or_condition"
    if field == "employee_limit" and any(
        marker in context for marker in ("과반수", "비율", "고용하고 유지", "고용하여 유지")
    ):
        return "relational_employee_condition"
    if field == "business_age_limit" and any(
        marker in context for marker in ("예비창업자", "사업자등록 말소", "최근")
    ):
        return "temporal_or_status_condition"
    return None


def _complex_limit_payload(field: str, text_value: str) -> dict[str, Any] | None:
    context = _limit_candidate_context(text_value, field)
    if not context:
        return None
    bounds = _bounds_from_evidence(field, context)
    branch_reason = _branching_limit_reason(context, field)
    # 후보 문맥 앞부분이 잘려 ①·②만 남는 경우가 있어, 전체 자격문맥에서
    # "모두 충족/모두 해당"이면 numbered_alternatives 오탐을 해제한다.
    if branch_reason == "numbered_alternatives" and re.search(
        r"(?:모두|전부|모든).{0,16}(?:충족|해당|요건)",
        _clean_text(text_value) or "",
    ):
        branch_reason = None
    if not bounds["has_alternatives"] and not branch_reason:
        return None
    result: dict[str, Any] = {
        "constraints": bounds["constraints"],
        "source_text": context,
        "extraction_method": "rule_ambiguous",
        "requires_manual_review": True,
        "logic": "any_of" if branch_reason else "all_of",
        "review_reason": branch_reason or "multiple_numeric_constraints",
    }
    if field == "sales_limit":
        result["unit"] = "krw"
    else:
        result["unit"] = "people" if field == "employee_limit" else "years"
    return result
