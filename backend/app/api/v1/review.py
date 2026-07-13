from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewUpload
from app.models.user import User
from app.schemas.review import (
    RequirementMatch,
    ReviewResponse,
    ReviewResult,
    ReviewStartResponse,
)
from app.services.review_documents import create_review_upload, run_review_pipeline

router = APIRouter()


@router.post(
    "",
    response_model=ReviewStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="신청 서류 검토 접수 (비동기)",
)
async def start_review(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="검토할 서류 (PDF/HWP/DOCX 등)"),
    policy_id: str | None = Form(None, description="신청 대상 정책 UUID (선택 — 있으면 요건 대조)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """서류를 접수하고 즉시 upload_id를 돌려준다. 검토는 백그라운드에서 진행된다.

    파이프라인(kordoc 추출 → 임베딩 → 요건 대조 → exaone3.5 진단)은 문서 길이에 따라
    수십 초에서 수 분이 걸린다. 동기로 응답하면 사용자가 스피너만 보며 몇 분을 기다리고,
    새로고침 한 번에 결과가 통째로 날아간다. 그래서 접수와 조회를 분리한다.

    진행 상태는 GET /api/v1/review/{upload_id} 로 폴링한다.
    """
    policy = _resolve_policy(db, policy_id)

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > settings.REVIEW_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다.")

    upload = create_review_upload(
        db,
        file_bytes=file_bytes,
        original_file_name=file.filename or "upload",
        content_type=file.content_type,
        policy=policy,
        user_id=current_user.id,
    )

    # 요청 세션(get_db)은 응답과 함께 닫히므로 백그라운드로 넘기면 안 된다.
    # 여기서는 id만 넘기고, 태스크가 자기 세션을 새로 연다.
    background_tasks.add_task(_run_review_job, upload.id)

    return ReviewStartResponse(
        upload_id=str(upload.id),
        policy_id=str(policy.id) if policy else None,
        review_status=upload.review_status,
        has_requirement_matching=policy is not None,
    )


@router.get("/{upload_id}", response_model=ReviewResponse, summary="검토 진행 상태·결과 조회 (폴링)")
def get_review(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upload = db.get(ReviewUpload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="검토 요청을 찾을 수 없습니다.")
    # 남의 검토 결과를 id만 알면 볼 수 있으면 안 된다.
    if upload.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="검토 요청을 찾을 수 없습니다.")

    return _to_response(upload)


def _run_review_job(upload_id: uuid.UUID) -> None:
    """백그라운드 검토 잡. 요청 세션과 무관한 자기 세션에서 돈다."""
    db = SessionLocal()
    try:
        upload = db.get(ReviewUpload, upload_id)
        if upload is None:
            return
        policy = db.get(NormalizedPolicy, upload.policy_id) if upload.policy_id else None
        run_review_pipeline(db, upload, policy=policy)
    except Exception as exc:  # noqa: BLE001 - 잡이 조용히 죽으면 사용자는 영원히 대기한다
        print(f"[review] 검토 잡 실패 upload_id={upload_id}: {exc}", flush=True)
        db.rollback()
        _mark_failed(db, upload_id, exc)
    finally:
        db.close()


def _mark_failed(db: Session, upload_id: uuid.UUID, exc: Exception) -> None:
    """잡이 예기치 않게 죽어도 행을 failed로 마감한다. 안 하면 '진행 중'에 영원히 머문다."""
    try:
        upload = db.get(ReviewUpload, upload_id)
        if upload is None:
            return
        upload.review_status = "failed"
        upload.diagnosis = upload.diagnosis or {
            "document_type": "unknown",
            "typos": [],
            "missing_fields": [],
            "format_issues": [],
            "missing_documents": [],
            "improvement_points": [],
            "overall": f"검토 중 오류가 발생했습니다: {exc}",
        }
        db.commit()
    except Exception as inner:  # noqa: BLE001
        print(f"[review] failed 마킹조차 실패 upload_id={upload_id}: {inner}", flush=True)
        db.rollback()


def _resolve_policy(db: Session, policy_id: str | None) -> NormalizedPolicy | None:
    if not policy_id:
        return None
    try:
        pid = uuid.UUID(policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="policy_id가 올바른 UUID가 아닙니다.")
    policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == pid).one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="해당 정책을 찾을 수 없습니다.")
    return policy


def _to_response(upload: ReviewUpload) -> ReviewResponse:
    diagnosis = upload.diagnosis
    result = None
    if diagnosis:
        result = ReviewResult(
            document_type=diagnosis.get("document_type", "unknown"),
            typos=diagnosis.get("typos", []),
            missing_fields=diagnosis.get("missing_fields", []),
            format_issues=diagnosis.get("format_issues", []),
            missing_documents=diagnosis.get("missing_documents", []),
            improvement_points=diagnosis.get("improvement_points", []),
            overall=diagnosis.get("overall", ""),
        )

    return ReviewResponse(
        upload_id=str(upload.id),
        policy_id=str(upload.policy_id) if upload.policy_id else None,
        review_status=upload.review_status,
        extraction_status=upload.extraction_status,
        requirement_matches=[RequirementMatch(**m) for m in (upload.requirement_matches or [])],
        result=result,
    )
