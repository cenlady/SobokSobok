import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.crud.policy import get_policy, get_program_page, list_policies, list_program_pages
from app.models.normalized_policy import NormalizedPolicy, AttachmentFile
from app.schemas.policy import (
    NormalizedPolicyDetailRead,
    PolicyAnnouncementDetailRead,
    PolicyAnnouncementRead,
    PolicyProgramPageDetailRead,
    PolicyProgramPageRead,
)

router = APIRouter()


@router.get("/", response_model=list[PolicyAnnouncementRead], summary="정책 공고 목록 조회")
def read_policies(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    return list_policies(db=db, skip=skip, limit=limit)


@router.get("/program-pages/", response_model=list[PolicyProgramPageRead], summary="SEMAS 지원사업 안내 페이지 목록 조회")
def read_program_pages(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    return list_program_pages(db=db, skip=skip, limit=limit)


@router.get(
    "/program-pages/{page_id}",
    response_model=PolicyProgramPageDetailRead,
    summary="SEMAS 지원사업 안내 페이지 상세 조회",
)
def read_program_page(page_id: int, db: Session = Depends(get_db)):
    page = get_program_page(db=db, page_id=page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Policy program page not found")
    return page


@router.get(
    "/normalized/{policy_id}",
    response_model=NormalizedPolicyDetailRead,
    summary="정규화 추천 정책 상세 조회",
)
def read_normalized_policy(policy_id: UUID, db: Session = Depends(get_db)):
    policy = db.get(NormalizedPolicy, policy_id)
    if policy is None or not policy.is_active:
        raise HTTPException(status_code=404, detail="Normalized policy not found")
    return policy


@router.get("/attachments/{file_id}/download", summary="정규화 공고 첨부파일 다운로드")
def download_attachment(file_id: UUID, db: Session = Depends(get_db)):
    file_info = db.get(AttachmentFile, file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    path = file_info.storage_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=file_info.original_file_name or "attachment"
    )


@router.get("/{pbanc_sn}", response_model=PolicyAnnouncementDetailRead, summary="정책 공고 상세 조회")
def read_policy(
    pbanc_sn: int,
    db: Session = Depends(get_db),
):
    policy = get_policy(db=db, pbanc_sn=pbanc_sn)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy announcement not found")
    return policy
