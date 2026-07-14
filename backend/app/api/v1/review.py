from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewSession
from app.models.user import User
from app.schemas.review import (
    FileDiagnosis,
    RequirementMatch,
    ReviewFile,
    ReviewResponse,
    ReviewStartResponse,
)
from app.services.review_documents import (
    UploadedFile,
    create_review_session,
    has_requirement_data,
    run_review_pipeline,
)

router = APIRouter()

# 한 번에 올릴 수 있는 파일 수. 정책이 요구하는 서류는 평균 3개, 최대 25개다.
MAX_FILES = 10


@router.post(
    "",
    response_model=ReviewStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="신청 서류 검토 접수 (여러 파일, 비동기)",
)
async def start_review(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="검토할 서류들 (PDF/HWP/DOCX 등)"),
    policy_id: str | None = Form(None, description="신청 대상 정책 UUID (선택 — 있으면 요건 대조)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """서류들을 접수하고 즉시 session_id를 돌려준다. 검토는 백그라운드에서 진행된다.

    파일을 여러 개 받는 이유: 정책은 평균 3개(최대 25개)의 서류를 요구한다.
    하나만 받으면 "사업자등록증 하나를 올렸더니 24개가 누락됐다"는, 맞지만 쓸모없는
    결과가 나온다. 준비한 서류를 다 올려야 '무엇이 빠졌는지'가 정보가 된다.

    진행 상태는 GET /api/v1/review/{session_id} 로 폴링한다.
    """
    if not files:
        raise HTTPException(status_code=400, detail="파일을 한 개 이상 올려주세요.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개까지 올릴 수 있어요.")

    policy = _resolve_policy(db, policy_id)

    uploaded: list[UploadedFile] = []
    total = 0
    for item in files:
        content = await item.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"'{item.filename}'이(가) 빈 파일입니다.")
        total += len(content)
        if total > settings.REVIEW_MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="전체 파일 크기가 너무 큽니다.")
        uploaded.append(
            UploadedFile(
                file_bytes=content,
                original_file_name=item.filename or "upload",
                content_type=item.content_type,
            )
        )

    session = create_review_session(db, files=uploaded, policy=policy, user_id=current_user.id)

    # 요건 대조 단계를 실제로 거치는지. 정책을 골랐어도 그 정책에 필수서류 정보가
    # 없으면(전체의 63%) 대조 단계가 없다. 프론트가 진행 단계 수를 여기에 맞춘다.
    will_match = policy is not None and has_requirement_data(db, policy)

    # 요청 세션(get_db)은 응답과 함께 닫히므로 백그라운드로 넘기면 안 된다.
    # 여기서는 id만 넘기고, 태스크가 자기 세션을 새로 연다.
    background_tasks.add_task(_run_review_job, session.id)

    return ReviewStartResponse(
        session_id=str(session.id),
        policy_id=str(policy.id) if policy else None,
        review_status=session.review_status,
        file_count=len(uploaded),
        has_requirement_matching=will_match,
    )


@router.get("/{session_id}", response_model=ReviewResponse, summary="검토 진행 상태·결과 조회 (폴링)")
def get_review(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.get(ReviewSession, session_id)
    # 남의 검토 결과를 id만 알면 볼 수 있으면 안 된다.
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="검토 요청을 찾을 수 없습니다.")

    return _to_response(session)


def _run_review_job(session_id: uuid.UUID) -> None:
    """백그라운드 검토 잡. 요청 세션과 무관한 자기 DB 세션에서 돈다."""
    db = SessionLocal()
    try:
        session = db.get(ReviewSession, session_id)
        if session is None:
            return
        policy = db.get(NormalizedPolicy, session.policy_id) if session.policy_id else None
        run_review_pipeline(db, session, policy=policy)
    except Exception as exc:  # noqa: BLE001 - 잡이 조용히 죽으면 사용자는 영원히 대기한다
        print(f"[review] 검토 잡 실패 session_id={session_id}: {exc}", flush=True)
        db.rollback()
        _mark_failed(db, session_id, exc)
    finally:
        db.close()


def _mark_failed(db: Session, session_id: uuid.UUID, exc: Exception) -> None:
    """잡이 예기치 않게 죽어도 세션을 failed로 마감한다. 안 하면 '진행 중'에 영원히 머문다."""
    try:
        session = db.get(ReviewSession, session_id)
        if session is None:
            return
        session.review_status = "failed"
        session.summary = session.summary or f"검토 중 오류가 발생했습니다: {exc}"
        db.commit()
    except Exception as inner:  # noqa: BLE001
        print(f"[review] failed 마킹조차 실패 session_id={session_id}: {inner}", flush=True)
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


def _to_response(session: ReviewSession) -> ReviewResponse:
    return ReviewResponse(
        session_id=str(session.id),
        policy_id=str(session.policy_id) if session.policy_id else None,
        review_status=session.review_status,
        requirement_status=session.requirement_status,
        requirement_matches=[
            RequirementMatch(**m) for m in (session.requirement_matches or [])
        ],
        files=[
            ReviewFile(
                upload_id=str(upload.id),
                file_name=upload.original_file_name,
                extraction_status=upload.extraction_status,
                diagnosis=FileDiagnosis(**upload.diagnosis) if upload.diagnosis else None,
            )
            for upload in session.uploads
        ],
        summary=session.summary,
        created_at=session.created_at,
    )
