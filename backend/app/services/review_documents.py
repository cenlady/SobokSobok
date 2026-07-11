from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rag_utils import (
    EmbeddingModel,
    OllamaEmbeddingModel,
    SimpleTextSplitter,
)
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewUpload, ReviewVector
from app.services.extract_attachments import _run_kordoc, _is_unsupported_name


def review_uploaded_document(
    db: Session,
    *,
    policy: NormalizedPolicy,
    file_bytes: bytes,
    original_file_name: str,
    content_type: str | None,
    user_id: int | None = None,
    embedding_model: EmbeddingModel | None = None,
) -> ReviewUpload:
    """업로드 서류를 추출→대조→LLM 진단하고 ReviewUpload에 결과를 저장해 반환한다.

    흐름:
      1. 업로드 파일 저장 + ReviewUpload 행 생성
      2. kordoc으로 텍스트 추출 (첨부 추출 로직 재사용)
      3. 업로드 텍스트를 청킹해 임베딩 (긴 문서 희석 방지)
      4. 정책 요건 벡터(review_vectors)와 대조 → 요건별 최고 유사도(후보 판정)
      5. exaone3.5 LLM이 원문 근거를 보고 최종 누락/보완 진단
    """
    embedder = embedding_model or OllamaEmbeddingModel(
        model_name=settings.REVIEW_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )

    # 1) 저장 + 행 생성
    upload = _persist_upload(db, policy, file_bytes, original_file_name, content_type, user_id)

    # 2) 텍스트 추출
    if _is_unsupported_name(original_file_name, content_type):
        upload.extraction_status = "unsupported"
        db.commit()
        upload.diagnosis = _fallback_result("파일 형식을 읽을 수 없어 진단하지 못했습니다.")
        db.commit()
        return upload

    try:
        extracted = _run_kordoc(upload.storage_path)
    except Exception as exc:  # noqa: BLE001
        upload.extraction_status = "failed"
        upload.diagnosis = _fallback_result(f"서류 텍스트 추출에 실패했습니다: {exc}")
        db.commit()
        return upload

    extracted = (extracted or "").strip()
    if not extracted:
        upload.extraction_status = "empty"
        upload.diagnosis = _fallback_result("서류에서 텍스트를 찾지 못했습니다(스캔 이미지일 수 있음).")
        db.commit()
        return upload

    upload.extracted_text = extracted
    upload.extraction_status = "success"
    db.commit()

    # 3) 업로드 청킹 + 임베딩
    splitter = SimpleTextSplitter(
        chunk_size=settings.REVIEW_CHUNK_SIZE,
        chunk_overlap=settings.REVIEW_CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(extracted) or [extracted[: settings.REVIEW_CHUNK_SIZE]]
    chunk_vectors = embedder.embed_documents(chunks)

    # 4) 요건별 대조 (요건 벡터 vs 업로드 청크 최고 유사도)
    matches = _match_requirements(db, policy, chunk_vectors)

    # 5) LLM 진단
    result = _diagnose_with_llm(policy, extracted, matches)

    upload.diagnosis = result
    db.commit()
    return upload


def _persist_upload(
    db: Session,
    policy: NormalizedPolicy,
    file_bytes: bytes,
    original_file_name: str,
    content_type: str | None,
    user_id: int | None,
) -> ReviewUpload:
    base = Path(settings.REVIEW_UPLOAD_DIR)
    base.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_file_name or "").suffix
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = base / stored_name
    stored_path.write_bytes(file_bytes)

    upload = ReviewUpload(
        user_id=user_id,
        policy_id=policy.id,
        original_file_name=original_file_name,
        storage_path=str(stored_path),
        content_type=content_type,
        file_size=len(file_bytes),
        extraction_status="pending",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _match_requirements(
    db: Session,
    policy: NormalizedPolicy,
    chunk_vectors: list[list[float]],
) -> list[dict]:
    """정책의 required_document 요건 각각에 대해 업로드 청크 중 최고 유사도를 구한다."""
    requirements = (
        db.query(ReviewVector)
        .filter(
            ReviewVector.policy_id == policy.id,
            ReviewVector.document_type == "required_document",
        )
        .all()
    )
    matches: list[dict] = []
    for req in requirements:
        best = max((_cosine(req.embedding, cv) for cv in chunk_vectors), default=0.0)
        matches.append(
            {
                "document_name": req.document_name,
                "best_similarity": round(float(best), 4),
                "likely_covered": best >= settings.REVIEW_CANDIDATE_THRESHOLD,
            }
        )
    matches.sort(key=lambda m: m["best_similarity"], reverse=True)
    return matches


def _diagnose_with_llm(policy: NormalizedPolicy, extracted: str, matches: list[dict]) -> dict:
    """exaone3.5로 최종 누락/보완 진단. 임베딩 후보는 힌트로만 제공한다."""
    required_names = [m["document_name"] for m in matches]
    covered = [m["document_name"] for m in matches if m["likely_covered"]]
    likely_missing = [m["document_name"] for m in matches if not m["likely_covered"]]

    prompt = _build_prompt(
        policy_title=policy.title,
        target_text=policy.target_text or "",
        required_names=required_names,
        covered=covered,
        likely_missing=likely_missing,
        extracted=extracted[:6000],
    )

    try:
        raw = _call_ollama_generate(prompt)
        parsed = _parse_llm_json(raw)
        if parsed is not None:
            return parsed
    except Exception as exc:  # noqa: BLE001 - LLM 실패 시 임베딩 결과로 폴백
        print(f"[review] LLM 진단 실패, 임베딩 폴백: {exc}", flush=True)

    # 폴백: 임베딩 후보만으로 최소 결과 구성
    return {
        "document_type": "unknown",
        "missing_items": likely_missing,
        "improvement_points": [],
        "overall": "자동 진단(LLM) 없이 임베딩 대조 결과만 제공합니다. 누락 후보를 확인해 주세요.",
    }


def _build_prompt(
    *,
    policy_title: str,
    target_text: str,
    required_names: list[str],
    covered: list[str],
    likely_missing: list[str],
    extracted: str,
) -> str:
    return f"""당신은 소상공인 정책 신청 서류를 검토하는 전문가입니다.
아래 정보를 바탕으로 사용자가 업로드한 서류의 누락/보완점을 진단하세요.

[정책] {policy_title}
[지원대상 요건] {target_text}

[정책이 요구하는 제출 서류]
{chr(10).join('- ' + n for n in required_names) or '- (명시된 필수서류 없음)'}

[임베딩 대조 힌트]
- 업로드 서류에 포함된 것으로 보이는 서류: {', '.join(covered) or '없음'}
- 누락 가능성이 있는 서류: {', '.join(likely_missing) or '없음'}
(힌트일 뿐이며, 실제 판단은 아래 업로드 서류 원문을 근거로 하세요.)

[업로드 서류 원문(일부)]
{extracted}

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 쓰지 마세요.
{{
  "document_type": "업로드 서류로 추정되는 유형(예: 사업자등록증, 사업계획서)",
  "missing_items": ["누락된 필수 서류나 항목"],
  "improvement_points": ["보완이 필요한 점"],
  "overall": "1~2문장 종합 진단"
}}"""


def _call_ollama_generate(prompt: str) -> str:
    with httpx.Client(timeout=settings.REVIEW_LLM_TIMEOUT_SECONDS) as client:
        resp = client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.REVIEW_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _parse_llm_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "document_type": str(data.get("document_type") or "unknown"),
        "missing_items": _as_str_list(data.get("missing_items")),
        "improvement_points": _as_str_list(data.get("improvement_points")),
        "overall": str(data.get("overall") or ""),
    }


def _as_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _fallback_result(message: str) -> dict:
    return {
        "document_type": "unknown",
        "missing_items": [],
        "improvement_points": [],
        "overall": message,
    }
