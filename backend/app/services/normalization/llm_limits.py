from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.normalized_policy import NormalizedPolicy
from app.services.normalization.common import _as_text, _clean_text, _make_hash
from app.services.normalization.limit_rules import (
    LIMIT_FIELD_SPECS,
    _bounds_from_evidence,
    _coerce_limit_int,
    _complex_limit_payload,
    _limit_candidate_context,
    _limit_fields_requiring_llm,
    _normalize_llm_operator,
    _select_limit_context,
)

# LLM 프롬프트나 응답 계약을 바꿀 때 반드시 올립니다.
# 원문이 같아도 이 값이 달라지면 기존 캐시를 사용하지 않습니다.
NORMALIZE_LLM_PROMPT_VERSION = "limit-structure-v1"

def _llm_cache_from_policy(policy: NormalizedPolicy | None) -> dict[str, Any] | None:
    if policy is None or not isinstance(policy.eligibility, dict):
        return None
    cache = policy.eligibility.get("llm_cache")
    return cache if isinstance(cache, dict) else None


def _llm_cache_context(text_value: str, field: str) -> str:
    return _select_limit_context(text_value, [field])


def _read_llm_cache_entry(
    existing_cache: dict[str, Any] | None,
    *,
    field: str,
    source_hash: str,
    context: str,
) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(existing_cache, dict):
        return False, None, None
    entry = existing_cache.get(field)
    if not isinstance(entry, dict) or "result" not in entry:
        return False, None, None
    if entry.get("source_hash") != source_hash:
        return False, None, None
    if entry.get("context_hash") != _make_hash(context):
        return False, None, None
    if entry.get("model") != settings.NORMALIZE_LLM_MODEL:
        return False, None, None
    if entry.get("prompt_version") != NORMALIZE_LLM_PROMPT_VERSION:
        return False, None, None
    result = entry.get("result")
    if result is not None and not isinstance(result, dict):
        return False, None, None
    return True, result, dict(entry)


def _make_llm_cache_entry(
    *,
    source_hash: str,
    context: str,
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_hash": source_hash,
        "context_hash": _make_hash(context),
        "model": settings.NORMALIZE_LLM_MODEL,
        "prompt_version": NORMALIZE_LLM_PROMPT_VERSION,
        "result": result,
    }


def _apply_llm_limit_result(
    limits: dict[str, dict[str, Any] | None],
    *,
    field: str,
    result: dict[str, Any] | None,
    complex_payload: dict[str, Any] | None,
) -> None:
    if result is None:
        return
    if complex_payload is not None and not result.get("requires_manual_review"):
        limits[field] = complex_payload
        return
    limits[field] = result
def _resolve_limits_with_llm_cache(
    text_value: str,
    parsed_limits: dict[str, dict[str, Any] | None],
    *,
    source_hash: str,
    existing_llm_cache: dict[str, Any] | None,
    log_label: str,
) -> tuple[dict[str, dict[str, Any] | None], dict[str, Any]]:
    limits = dict(parsed_limits)
    llm_fields = _limit_fields_requiring_llm(text_value, limits)
    if not llm_fields:
        return limits, {}

    complex_payloads: dict[str, dict[str, Any] | None] = {}
    complex_fields: list[str] = []
    for field in llm_fields:
        complex_payload = _complex_limit_payload(field, text_value)
        complex_payloads[field] = complex_payload
        if complex_payload is not None:
            limits[field] = complex_payload
            complex_fields.append(field)
    if complex_fields:
        print(
            f"  [LLM Structure] {log_label} 복합 조건 구조화 요청: {complex_fields}",
            flush=True,
        )

    llm_cache: dict[str, Any] = {}
    cache_hits: list[str] = []
    pending_fields: list[str] = []
    for field in llm_fields:
        context = _llm_cache_context(text_value, field)
        hit, cached_result, cache_entry = _read_llm_cache_entry(
            existing_llm_cache,
            field=field,
            source_hash=source_hash,
            context=context,
        )
        if not hit or cache_entry is None:
            pending_fields.append(field)
            continue
        llm_cache[field] = cache_entry
        cache_hits.append(field)
        _apply_llm_limit_result(
            limits,
            field=field,
            result=cached_result,
            complex_payload=complex_payloads[field],
        )

    if cache_hits:
        print(f"  [LLM Cache] {log_label} 결과 재사용: {cache_hits}", flush=True)

    if pending_fields and settings.REC_OLLAMA_BASE_URL:
        print(f"  [Ollama] {log_label} 규칙 판정 보완: {pending_fields}", flush=True)
        cacheable_fields: set[str] = set()
        llm_limits = _extract_limits_via_ollama(
            text_value,
            pending_fields,
            cacheable_fields=cacheable_fields,
        )
        for field in pending_fields:
            result = llm_limits.get(field)
            _apply_llm_limit_result(
                limits,
                field=field,
                result=result,
                complex_payload=complex_payloads[field],
            )
            if field in cacheable_fields:
                llm_cache[field] = _make_llm_cache_entry(
                    source_hash=source_hash,
                    context=_llm_cache_context(text_value, field),
                    result=result,
                )
        filled = [field for field in pending_fields if limits[field] is not None]
        print(f"  [Ollama] {log_label} 결과 적용: {filled if filled else '추출 없음'}", flush=True)

    return limits, llm_cache


def _convert_llm_limit(
    field: str,
    raw_value: Any,
    context: str,
    model_name: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_value, dict):
        return None

    evidence = _clean_text(_as_text(raw_value.get("evidence")))
    if not evidence or evidence not in context:
        return None
    if not _limit_candidate_context(evidence, field):
        return None

    maximum = int(LIMIT_FIELD_SPECS[field]["maximum"])
    evidence_bounds = _bounds_from_evidence(field, evidence)
    classification = (_as_text(raw_value.get("classification")) or "direct").lower()
    logic = (_as_text(raw_value.get("logic")) or "all_of").lower()
    scope = (_as_text(raw_value.get("scope")) or "global").lower()
    if classification in {"unrelated", "none", "not_eligibility"}:
        return None
    if classification in {"alternative", "complex", "relational"} or scope != "global":
        result: dict[str, Any] = {
            "constraints": evidence_bounds["constraints"],
            "source_text": evidence,
            "extraction_method": "ollama_structure",
            "model": model_name,
            "prompt_version": NORMALIZE_LLM_PROMPT_VERSION,
            "requires_manual_review": True,
            "logic": logic if logic in {"all_of", "any_of"} else "any_of",
            "review_reason": classification,
            "scope": scope,
        }
        result["unit"] = (
            "krw"
            if field == "sales_limit"
            else "people" if field == "employee_limit" else "years"
        )
        return result

    min_value = _coerce_limit_int(evidence_bounds["min_value"], maximum)
    max_value = _coerce_limit_int(evidence_bounds["max_value"], maximum)
    # evidence에서 하나라도 유효한 경계를 복구했다면, 모델이 별도로 생성한
    # 반대쪽 숫자는 신뢰하지 않는다. 다른 금액(임차료·지원금)을 min/max로
    # 끌어오는 소형 모델의 오탐을 막기 위한 규칙이다.
    if not evidence_bounds["constraints"]:
        min_value = _coerce_limit_int(raw_value.get("min"), maximum)
        max_value = _coerce_limit_int(raw_value.get("max"), maximum)
    min_operator = _as_text(evidence_bounds["min_operator"])
    max_operator = _as_text(evidence_bounds["max_operator"])
    if min_value is not None and min_operator is None:
        min_operator = _normalize_llm_operator(raw_value.get("min_operator"), "min", evidence)
    if max_value is not None and max_operator is None:
        max_operator = _normalize_llm_operator(raw_value.get("max_operator"), "max", evidence)

    if min_value is not None and min_operator is None:
        min_value = None
    if max_value is not None and max_operator is None:
        max_value = None
    if min_value is None and max_value is None:
        return None
    if min_value is not None and max_value is not None and min_value > max_value:
        return None

    result: dict[str, Any] = {
        "min_value": min_value,
        "min_operator": min_operator,
        "max_value": max_value,
        "max_operator": max_operator,
        "source_text": evidence,
        "extraction_method": "ollama_llm",
        "model": model_name,
        "prompt_version": NORMALIZE_LLM_PROMPT_VERSION,
    }
    if field == "sales_limit":
        result["min_amount_krw"] = min_value
        result["max_amount_krw"] = max_value
        if (min_value is None) != (max_value is None):
            result["amount_krw"] = max_value if max_value is not None else min_value
            result["operator"] = max_operator if max_value is not None else min_operator
    else:
        result["unit"] = "people" if field == "employee_limit" else "years"
        if (min_value is None) != (max_value is None):
            result["value"] = max_value if max_value is not None else min_value
            result["operator"] = max_operator if max_value is not None else min_operator
    return result


def _is_explicit_llm_no_match(field: str, raw_value: Any, context: str) -> bool:
    if not isinstance(raw_value, dict):
        return False
    classification = (_as_text(raw_value.get("classification")) or "").lower()
    if classification not in {"unrelated", "none", "not_eligibility"}:
        return False
    evidence = _clean_text(_as_text(raw_value.get("evidence")))
    return bool(
        evidence
        and evidence in context
        and _limit_candidate_context(evidence, field)
    )


def _extract_limits_via_ollama(
    text_value: str | None,
    requested_fields: list[str] | None = None,
    *,
    cacheable_fields: set[str] | None = None,
) -> dict[str, Any]:
    """규칙으로 확정하지 못한 조건을 구조화하되, 근거는 코드로 재검증합니다."""
    fallback_res = {field: None for field in LIMIT_FIELD_SPECS}
    clean_txt = _clean_text(text_value)
    if not clean_txt:
        return fallback_res

    fields = [field for field in (requested_fields or LIMIT_FIELD_SPECS.keys()) if field in LIMIT_FIELD_SPECS]
    fields = [field for field in fields if _limit_candidate_context(clean_txt, field)]
    if not fields:
        return fallback_res

    model_name = settings.NORMALIZE_LLM_MODEL
    base_url = settings.REC_OLLAMA_BASE_URL
    if not base_url:
        return fallback_res

    field_prompts = {
        "employee_limit": (
            "사업체 직원수 또는 상시근로자수 조건",
            "입력 '상시근로자 5인 미만'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":null,"min_operator":null,"max":5,"max_operator":"<","evidence":"상시근로자 5인 미만"}',
        ),
        "sales_limit": (
            "사업체의 연간 매출액 조건",
            "입력 '연매출 10억원 이하'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":null,"min_operator":null,"max":1000000000,"max_operator":"<=","evidence":"연매출 10억원 이하"}',
        ),
        "business_age_limit": (
            "사업체의 창업 후 업력 조건",
            "입력 '창업 3년 이상 7년 이하'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":3,"min_operator":">=","max":7,"max_operator":"<=","evidence":"창업 3년 이상 7년 이하"}',
        ),
    }

    for field in fields:
        complex_payload = _complex_limit_payload(field, clean_txt)
        context = _select_limit_context(clean_txt, [field])
        description, example = field_prompts[field]
        system_prompt = (
            f"당신은 소상공인 지원 공고에서 {description} 하나만 추출합니다. "
            "반드시 classification, logic, scope, min, min_operator, max, max_operator, evidence 키를 가진 "
            "단일 JSON 객체를 반환하세요. classification은 direct, alternative, relational, unrelated 중 하나입니다. "
            "logic은 all_of 또는 any_of, scope는 global 또는 branch입니다. "
            "미만은 <, 이하는 <=, 초과는 >, 이상은 >= 입니다. "
            "명시된 숫자 조건이 없을 때만 min과 max를 null로 두세요. "
            "소상공인이라는 단어만으로 기준을 추정하지 마세요. "
            "지원금액, 대표자 나이, 예상 매출은 자격조건으로 해석하지 마세요. "
            "각 호 중 하나, 또는, 자금별·업종별 조건은 direct로 평탄화하지 마세요. "
            "매출액은 원 단위 정수로 환산하고, 양쪽 범위는 min과 max를 모두 보존하세요. "
            "evidence는 해당 필드의 숫자 조건이 담긴 가장 짧은 연속 원문만 그대로 복사하고, "
            "임차료·지원금·대표자 나이·신용점수 등 다른 숫자는 포함하지 마세요. "
            f"출력 예시: {example}. JSON 이외의 문장은 출력하지 마세요."
        )
        print(f"  [Ollama Structure] {model_name} 호출: field={field}, chars={len(context)}", flush=True)
        try:
            response = httpx.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=settings.NORMALIZE_LLM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            response_text = payload.get("message", {}).get("content", "").strip()
            data = json.loads(response_text)
            if isinstance(data, dict) and isinstance(data.get(field), dict):
                data = data[field]
            explicit_no_match = _is_explicit_llm_no_match(field, data, context)
            converted = _convert_llm_limit(field, data, context, model_name)
            if complex_payload is not None:
                # 규칙 단계에서 복합 가능성이 확인된 필드는 모델이 direct라고
                # 잘못 분류해도 단일 컬럼으로 평탄화하지 않는다.
                fallback_res[field] = (
                    converted
                    if converted and converted.get("requires_manual_review")
                    else complex_payload
                )
            else:
                fallback_res[field] = converted
            # HTTP 호출과 JSON 파싱까지 성공했다면 검증 거절도 안전한 음성 결과로
            # 캐시합니다. 거절된 값 자체는 적용하지 않으며, 원문·모델·프롬프트가
            # 바뀌면 캐시 키가 달라져 다시 호출됩니다.
            if cacheable_fields is not None:
                cacheable_fields.add(field)
            if fallback_res[field] is None and not explicit_no_match:
                print(f"  [Ollama Structure] 검증에서 거절된 응답: {response_text[:500]}", flush=True)
        except Exception as exc:
            fallback_res[field] = complex_payload
            print(f"  [Ollama Structure] {field} 추출 실패: {exc}", flush=True)
    return fallback_res
