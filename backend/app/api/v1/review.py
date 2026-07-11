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


@router.post("", response_model=ReviewResponse, summary="신청 서류 검토 (OCR + RAG 진단)")
async def review_document(
    file: UploadFile = File(..., description="검토할 서류 (PDF/HWP/이미지 등)"),
    policy_id: str = Form(..., description="검토 대상 정책 UUID"),
    db: Session = Depends(get_db),
):
    # 정책 확인
    try:
        pid = uuid.UUID(policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="policy_id가 올바른 UUID가 아닙니다.")

    policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == pid).one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="해당 정책을 찾을 수 없습니다.")

    # 파일 크기 제한
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > settings.REVIEW_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다.")

    upload = review_uploaded_document(
        db,
        policy=policy,
        file_bytes=file_bytes,
        original_file_name=file.filename or "upload",
        content_type=file.content_type,
    )

    diagnosis = upload.diagnosis or {}
    return ReviewResponse(
        upload_id=str(upload.id),
        policy_id=str(policy.id),
        extraction_status=upload.extraction_status,
        requirement_matches=[],  # 상세 매칭은 진단 근거로 내부 사용, 필요 시 확장
        result=ReviewResult(
            document_type=diagnosis.get("document_type", "unknown"),
            missing_items=diagnosis.get("missing_items", []),
            improvement_points=diagnosis.get("improvement_points", []),
            overall=diagnosis.get("overall", ""),
        ),
    )
