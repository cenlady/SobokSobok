from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewUpload
from app.services.extract_attachments import _run_kordoc, _is_unsupported_name


def review_uploaded_document(
    db: Session,
    *,
    file_bytes: bytes,
    original_file_name: str,
    content_type: str | None,
    policy: NormalizedPolicy | None = None,
    user_id: int | None = None,
) -> ReviewUpload:
    """업로드 서류 자체를 검토(오타·빈칸·형식)하고 결과를 저장해 반환한다.

    흐름:
      1. 업로드 파일 저장 + ReviewUpload 행 생성
      2. kordoc으로 텍스트 추출
      3. exaone3.5 LLM이 서류 자체를 검토 (오타/빠진 항목/형식 오류/보완점)

    정책 요건과의 대조는 하지 않는다. policy가 주어지면 "무슨 신청용 서류인지"
    맥락으로만 참고한다(없어도 검토 가능).
    """
    # 1) 저장 + 행 생성
    upload = _persist_upload(db, file_bytes, original_file_name, content_type, policy, user_id)

    # 2) 텍스트 추출
    if _is_unsupported_name(original_file_name, content_type):
        upload.extraction_status = "unsupported"
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

    # 3) LLM이 서류 자체를 검토
    upload.diagnosis = _diagnose_with_llm(extracted, policy)
    db.commit()
    return upload


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


def _diagnose_with_llm(extracted: str, policy: NormalizedPolicy | None) -> dict:
    """exaone3.5로 서류 자체를 검토한다. LLM 실패 시 안내 폴백."""
    prompt = _build_prompt(extracted[:6000], policy)
    try:
        raw = _call_ollama_generate(prompt)
        parsed = _parse_llm_json(raw)
        if parsed is not None:
            return parsed
    except Exception as exc:  # noqa: BLE001
        print(f"[review] LLM 진단 실패: {exc}", flush=True)
    return _fallback_result("자동 진단(LLM)에 실패했습니다. 잠시 후 다시 시도해 주세요.")


def _build_prompt(extracted: str, policy: NormalizedPolicy | None) -> str:
    context = ""
    if policy is not None:
        context = f"\n[참고] 이 서류는 '{policy.title}' 신청용으로 추정됩니다. 해당 맥락도 고려하세요.\n"

    return f"""당신은 소상공인 정책 신청 서류를 꼼꼼히 검토하는 전문가입니다.
아래 업로드된 서류 '자체'를 검토하여 오타, 빠진 항목, 형식 오류, 보완점을 찾아내세요.
정책 요건과의 대조가 아니라, 이 서류 문서 자체의 완성도를 봅니다.
{context}
검토 관점:
- 오타/맞춤법: 잘못 쓰인 단어, 띄어쓰기 오류 등
- 빠진 항목: 비어 있는 칸, 작성되지 않은 필수 항목(성명·연락처·날짜·서명 등)
- 형식 오류: 날짜 형식, 금액 표기, 표/양식이 어긋난 부분
- 보완점: 내용이 불명확하거나 근거가 부족해 추가하면 좋을 부분

[업로드 서류 원문(일부)]
{extracted}

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 쓰지 마세요.
해당 항목이 없으면 빈 배열([])로 두세요.
{{
  "document_type": "서류로 추정되는 유형(예: 사업계획서, 지원신청서)",
  "typos": ["오타/맞춤법 오류: '원문' → '제안'"],
  "missing_fields": ["비어 있거나 빠진 항목"],
  "format_issues": ["형식/양식 오류"],
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
        "improvement_points": [],
        "overall": message,
    }
