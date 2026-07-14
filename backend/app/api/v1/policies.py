import os
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.crud.policy import (
    get_policy,
    get_program_page,
    list_normalized_policies,
    list_policies,
    list_program_pages,
)
from app.models.normalized_policy import NormalizedPolicy, AttachmentFile
from app.services.recommend import classify_need_tags
from app.schemas.policy import (
    NormalizedPolicyDetailRead,
    NormalizedPolicyListRead,
    NormalizedPolicyListResponse,
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
    "/normalized/",
    response_model=NormalizedPolicyListResponse,
    summary="정규화 정책 목록 조회 (전체 정책 조회용)",
)
def read_normalized_policies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="제목·요약 검색어"),
    support_type: str | None = Query(default=None, description="지원 유형 필터"),
    sido: str | None = Query(default=None, description="시/도 필터 (전국 공고는 항상 포함)"),
    category: Literal[
        "funding",
        "education_consulting",
        "digital",
        "marketing",
        "facility",
        "recovery",
        "employment",
    ] | None = Query(default=None, description="사용자용 지원 분야 필터"),
    status: Literal["available", "all", "open", "notice", "closed"] = Query(
        default="available",
        description="available=접수중·공고예정(마감 제외), all=전체",
    ),
    sort: Literal["deadline", "latest"] = Query(
        default="deadline",
        description="deadline=마감 임박순, latest=최신 등록순",
    ),
    db: Session = Depends(get_db),
):
    policies, total = list_normalized_policies(
        db,
        skip=skip,
        limit=limit,
        q=q,
        support_type=support_type,
        sido=sido,
        category=category,
        status=status,
        sort=sort,
    )
    items = [
        NormalizedPolicyListRead.model_validate(policy).model_copy(
            update={"categories": classify_need_tags(policy)},
        )
        for policy in policies
    ]
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_next": skip + len(items) < total,
    }


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
