from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.normalized_policy import NormalizedPolicy
from app.schemas.review import ReviewResponse, ReviewResult
from app.services.review_documents import review_uploaded_document

router = APIRouter()


@router.post("", response_model=ReviewResponse, summary="신청 서류 자체 검토 (오타·빈칸·형식)")
async def review_document(
    file: UploadFile = File(..., description="검토할 서류 (PDF/HWP/DOCX 등)"),
    policy_id: str | None = Form(None, description="신청 대상 정책 UUID (선택 — 맥락 참고용)"),
    db: Session = Depends(get_db),
):
    # 정책은 선택 — 주어지면 맥락으로만 사용
    policy: NormalizedPolicy | None = None
    if policy_id:
        try:
            pid = uuid.UUID(policy_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="policy_id가 올바른 UUID가 아닙니다.")
        policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == pid).one_or_none()
        if policy is None:
            raise HTTPException(status_code=404, detail="해당 정책을 찾을 수 없습니다.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > settings.REVIEW_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다.")

    upload = review_uploaded_document(
        db,
        file_bytes=file_bytes,
        original_file_name=file.filename or "upload",
        content_type=file.content_type,
        policy=policy,
    )

    diagnosis = upload.diagnosis or {}
    return ReviewResponse(
        upload_id=str(upload.id),
        policy_id=str(policy.id) if policy else None,
        extraction_status=upload.extraction_status,
        result=ReviewResult(
            document_type=diagnosis.get("document_type", "unknown"),
            typos=diagnosis.get("typos", []),
            missing_fields=diagnosis.get("missing_fields", []),
            format_issues=diagnosis.get("format_issues", []),
            improvement_points=diagnosis.get("improvement_points", []),
            overall=diagnosis.get("overall", ""),
        ),
    )
