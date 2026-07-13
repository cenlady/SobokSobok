from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.services.normalization.common import _as_text, _clean_text, _make_hash
from app.services.normalization.documents import _document_name_key


DOCUMENT_LLM_CACHE_KEY = "required_documents"
DOCUMENT_LLM_PROMPT_VERSION = "document-candidate-v3"
MAX_DOCUMENT_LLM_CANDIDATES = 8


def _resolve_required_documents_with_llm_cache(
    candidates: list[dict[str, str]],
    *,
    source: str,
    source_hash: str,
    existing_llm_cache: dict[str, Any] | None,
    log_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique_candidates = _unique_candidates(candidates)[:MAX_DOCUMENT_LLM_CANDIDATES]
    if not unique_candidates:
        return [], {}

    documents: list[dict[str, Any]] = []
    cache_entries: dict[str, Any] = {}
    pending: list[dict[str, str]] = []
    cache_hits = 0

    for candidate_item in unique_candidates:
        candidate = candidate_item["name"]
        context = candidate_item["context"]
        hit, accepted, entry = _read_document_cache_entry(
            existing_llm_cache,
            candidate=candidate,
            context=context,
            source_hash=source_hash,
        )
        if not hit or entry is None:
            pending.append(candidate_item)
            continue
        cache_entries[_make_hash(candidate)] = entry
        cache_hits += 1
        if accepted:
            documents.append(_llm_document_item(candidate, source))

    if cache_hits:
        print(
            f"  [LLM Document Cache] {log_label} 후보 결과 재사용: {cache_hits}",
            flush=True,
        )

    accepted_count = 0
    if pending and settings.REC_OLLAMA_BASE_URL:
        print(
            f"  [Ollama Documents] {log_label} 문서 후보 판정: {len(pending)}",
            flush=True,
        )
        for candidate_item in pending:
            candidate = candidate_item["name"]
            context = candidate_item["context"]
            accepted, cacheable = _classify_document_candidate_via_ollama(candidate)
            if not cacheable:
                continue
            cache_entries[_make_hash(candidate)] = _make_document_cache_entry(
                candidate=candidate,
                context=context,
                source_hash=source_hash,
                accepted=bool(accepted),
            )
            if accepted:
                documents.append(_llm_document_item(candidate, source))
                accepted_count += 1
        print(
            f"  [Ollama Documents] {log_label} 추가 문서명: {accepted_count}",
            flush=True,
        )

    if not cache_entries:
        return documents, {}
    return documents, {
        DOCUMENT_LLM_CACHE_KEY: {
            "model": settings.NORMALIZE_LLM_MODEL,
            "prompt_version": DOCUMENT_LLM_PROMPT_VERSION,
            "entries": cache_entries,
        }
    }


def _classify_document_candidate_via_ollama(candidate: str) -> tuple[bool | None, bool]:
    model_name = settings.NORMALIZE_LLM_MODEL
    base_url = settings.REC_OLLAMA_BASE_URL
    if not base_url:
        return None, False

    system_prompt = (
        "당신은 소상공인 지원 공고의 명시적인 제출서류 구간에서 후보 한 줄만 판정합니다. "
        "후보가 신청자가 준비하거나 제출할 구체적인 문서·파일의 이름 또는 종류를 가리키는 "
        "명사구이면 document입니다. 추천서, 명부, 내역, 증빙, 수료증, 자격증, 영수증, "
        "소개서, 확약서, 동의서, 사진, 원본, 전자세금계산서는 document입니다. "
        "앞에 제출 대상이나 조건 설명이 붙어도 전체 후보가 구체적인 문서를 가리키면 document입니다. "
        "제목·기관·장소·안내문·행동지시 또는 구체적인 이름이 없는 '자료/서류' 표현은 "
        "not_document입니다. "
        "문서명을 새로 만들거나 고쳐 쓰지 마세요. "
        "classification 키만 가진 단일 JSON 객체를 반환하세요. "
        "예시 입력 '업체 소개서'의 출력은 "
        "{\"classification\":\"document\"}입니다. "
        "예시 입력 '온라인으로 제출하세요'의 출력은 "
        "{\"classification\":\"not_document\"}입니다."
    )
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": candidate},
                ],
                "format": {
                    "type": "object",
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": ["document", "not_document"],
                        },
                    },
                    "required": ["classification"],
                    "additionalProperties": False,
                },
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=settings.NORMALIZE_LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_text = response.json().get("message", {}).get("content", "").strip()
        data = json.loads(response_text)
        classification = (_as_text(data.get("classification")) or "").lower()
        if classification not in {"document", "not_document"}:
            print(
                f"  [Ollama Documents] 검증에서 거절된 응답: {response_text[:300]}",
                flush=True,
            )
            return False, True
        return classification == "document", True
    except Exception as exc:
        print(f"  [Ollama Documents] 후보 판정 실패: {exc}", flush=True)
        return None, False


def _read_document_cache_entry(
    existing_cache: dict[str, Any] | None,
    *,
    candidate: str,
    context: str,
    source_hash: str,
) -> tuple[bool, bool, dict[str, Any] | None]:
    if not isinstance(existing_cache, dict):
        return False, False, None
    group = existing_cache.get(DOCUMENT_LLM_CACHE_KEY)
    if not isinstance(group, dict):
        return False, False, None
    entries = group.get("entries")
    if not isinstance(entries, dict):
        return False, False, None
    entry = entries.get(_make_hash(candidate))
    if not isinstance(entry, dict):
        return False, False, None
    if entry.get("source_hash") != source_hash:
        return False, False, None
    if entry.get("context_hash") != _make_hash(context):
        return False, False, None
    if entry.get("model") != settings.NORMALIZE_LLM_MODEL:
        return False, False, None
    if entry.get("prompt_version") != DOCUMENT_LLM_PROMPT_VERSION:
        return False, False, None
    result = entry.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("accepted"), bool):
        return False, False, None
    return True, bool(result["accepted"]), dict(entry)


def _make_document_cache_entry(
    *,
    candidate: str,
    context: str,
    source_hash: str,
    accepted: bool,
) -> dict[str, Any]:
    return {
        "source_hash": source_hash,
        "context_hash": _make_hash(context),
        "model": settings.NORMALIZE_LLM_MODEL,
        "prompt_version": DOCUMENT_LLM_PROMPT_VERSION,
        "result": {"accepted": accepted},
    }


def _llm_document_item(candidate: str, source: str) -> dict[str, Any]:
    return {
        "name": candidate,
        "description": "",
        "source": source,
        "confidence": 0.72,
        "extraction_method": "ollama_document_candidate",
    }


def _unique_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        text_value = _clean_text(candidate.get("name"))
        context = _clean_text(candidate.get("context"))
        key = _document_name_key(text_value)
        if (
            not text_value
            or not context
            or not key
            or key in seen
            or not _candidate_occurs_in_context(text_value, context)
        ):
            continue
        seen.add(key)
        values.append({"name": text_value, "context": context})
    return values


def _candidate_occurs_in_context(candidate: str, context: str) -> bool:
    candidate_text = "".join((_clean_text(candidate) or "").split())
    context_text = "".join((_clean_text(context) or "").split())
    return bool(candidate_text and candidate_text in context_text)
