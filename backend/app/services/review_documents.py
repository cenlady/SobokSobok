from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rag_utils import EmbeddingModel, OllamaEmbeddingModel, SimpleTextSplitter
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewUpload, ReviewVector
from app.services.extract_attachments import _run_kordoc, _is_unsupported_name


def review_uploaded_document(
    db: Session,
    *,
    file_bytes: bytes,
    original_file_name: str,
    content_type: str | None,
    policy: NormalizedPolicy | None = None,
    user_id: int | None = None,
    embedding_model: EmbeddingModel | None = None,
) -> tuple[ReviewUpload, list[dict]]:
    """업로드 서류를 검토하고 결과를 저장해 반환한다. (하이브리드)

    흐름:
      1. 업로드 파일 저장 + ReviewUpload 행 생성
      2. kordoc으로 텍스트 추출
      3. policy가 있으면: 업로드 청킹→임베딩→review_vectors 요건 대조(RAG)
      4. exaone3.5 LLM이 [서류 원문 + 요건 대조 근거]로 종합 진단
         - 자체 검토(오타·빈칸·형식) + 요건 대조(누락 서류)

    policy가 없으면 요건 대조는 건너뛰고 서류 자체 검토만 수행한다.
    반환: (ReviewUpload, requirement_matches)
    """
    upload = _persist_upload(db, file_bytes, original_file_name, content_type, policy, user_id)

    # 텍스트 추출
    if _is_unsupported_name(original_file_name, content_type):
        upload.extraction_status = "unsupported"
        upload.diagnosis = _fallback_result("파일 형식을 읽을 수 없어 진단하지 못했습니다.")
        db.commit()
        return upload, []

    try:
        extracted = _run_kordoc(upload.storage_path)
    except Exception as exc:  # noqa: BLE001
        upload.extraction_status = "failed"
        upload.diagnosis = _fallback_result(f"서류 텍스트 추출에 실패했습니다: {exc}")
        db.commit()
        return upload, []

    extracted = (extracted or "").strip()
    if not extracted:
        upload.extraction_status = "empty"
        upload.diagnosis = _fallback_result("서류에서 텍스트를 찾지 못했습니다(스캔 이미지일 수 있음).")
        db.commit()
        return upload, []

    upload.extracted_text = extracted
    upload.extraction_status = "success"
    db.commit()

    # policy가 있으면 RAG 요건 대조
    matches: list[dict] = []
    if policy is not None:
        embedder = embedding_model or OllamaEmbeddingModel(
            model_name=settings.REVIEW_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
        splitter = SimpleTextSplitter(
            chunk_size=settings.REVIEW_CHUNK_SIZE,
            chunk_overlap=settings.REVIEW_CHUNK_OVERLAP,
        )
        chunks = splitter.split_text(extracted) or [extracted[: settings.REVIEW_CHUNK_SIZE]]
        chunk_vectors = embedder.embed_documents(chunks)
        matches = _match_requirements(db, policy, chunk_vectors)

    # LLM 종합 진단
    upload.diagnosis = _diagnose_with_llm(extracted, policy, matches)
    db.commit()
    return upload, matches


def _persist_upload(
    db: Session,
    file_bytes: bytes,
    original_file_name: str,
    content_type: str | None,
    policy: NormalizedPolicy | None,
    user_id: int | None,
) -> ReviewUpload:
    base = Path(settings.REVIEW_UPLOAD_DIR)
    base.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_file_name or "").suffix
    stored_path = base / f"{uuid.uuid4().hex}{suffix}"
    stored_path.write_bytes(file_bytes)

    upload = ReviewUpload(
        user_id=user_id,
        policy_id=policy.id if policy else None,
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


def _match_requirements(db: Session, policy: NormalizedPolicy, chunk_vectors: list[list[float]]) -> list[dict]:
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


def _diagnose_with_llm(extracted: str, policy: NormalizedPolicy | None, matches: list[dict]) -> dict:
    """exaone3.5로 서류 자체 검토 + (있으면) 요건 대조 종합 진단."""
    prompt = _build_prompt(extracted[:6000], policy, matches)
    try:
        raw = _call_ollama_generate(prompt)
        parsed = _parse_llm_json(raw)
        if parsed is not None:
            return parsed
    except Exception as exc:  # noqa: BLE001
        print(f"[review] LLM 진단 실패: {exc}", flush=True)
    # 폴백: 임베딩 후보만으로 누락 서류 구성
    likely_missing = [m["document_name"] for m in matches if not m["likely_covered"]]
    return {
        "document_type": "unknown",
        "typos": [],
        "missing_fields": [],
        "format_issues": [],
        "missing_documents": likely_missing,
        "improvement_points": [],
        "overall": "자동 진단(LLM)에 실패했습니다. 임베딩 대조 기준 누락 후보만 표시합니다.",
    }


def _build_prompt(extracted: str, policy: NormalizedPolicy | None, matches: list[dict]) -> str:
    # 서류 자체 검토는 항상 수행, 요건 대조는 policy가 있을 때만 프롬프트에 포함
    requirement_block = ""
    if policy is not None:
        required_names = [m["document_name"] for m in matches]
        covered = [m["document_name"] for m in matches if m["likely_covered"]]
        likely_missing = [m["document_name"] for m in matches if not m["likely_covered"]]
        requirement_block = f"""
[정책 요건 대조] 이 서류는 '{policy.title}' 신청용으로 추정됩니다.
- 정책이 요구하는 서류: {', '.join(required_names) or '(명시된 필수서류 없음)'}
- 업로드 서류에 포함된 것으로 보이는 서류(임베딩 힌트): {', '.join(covered) or '없음'}
- 누락 가능성이 있는 서류(임베딩 힌트): {', '.join(likely_missing) or '없음'}
(힌트일 뿐이며, 실제 판단은 아래 업로드 원문을 근거로 하세요. missing_documents에 반영.)
"""

    return f"""당신은 소상공인 정책 신청 서류를 꼼꼼히 검토하는 전문가입니다.
업로드된 서류를 (1) 서류 자체의 완성도와 (2) 정책 요건 충족 관점에서 검토하세요.

[서류 자체 검토 관점]
- 오타/맞춤법: 잘못 쓰인 단어, 띄어쓰기 오류
- 빠진 항목: 비어 있는 칸, 미작성 필수 항목(성명·연락처·날짜·서명 등)
- 형식 오류: 날짜/금액 표기, 표·양식이 어긋난 부분
{requirement_block}
[업로드 서류 원문(일부)]
{extracted}

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 쓰지 마세요.
해당 항목이 없으면 빈 배열([])로 두세요.
{{
  "document_type": "서류로 추정되는 유형(예: 사업계획서, 지원신청서)",
  "typos": ["오타/맞춤법: '원문' → '제안'"],
  "missing_fields": ["비어 있거나 빠진 항목"],
  "format_issues": ["형식/양식 오류"],
  "missing_documents": ["정책 요구 서류 중 누락된 것 (요건 대조 시)"],
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
        "typos": _as_str_list(data.get("typos")),
        "missing_fields": _as_str_list(data.get("missing_fields")),
        "format_issues": _as_str_list(data.get("format_issues")),
        "missing_documents": _as_str_list(data.get("missing_documents")),
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
        "typos": [],
        "missing_fields": [],
        "format_issues": [],
        "missing_documents": [],
        "improvement_points": [],
        "overall": message,
    }
