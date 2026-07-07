from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud.policy import get_policy, get_program_page, list_policies, list_program_pages
from app.schemas.policy import (
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


@router.get("/{pbanc_sn}", response_model=PolicyAnnouncementDetailRead, summary="정책 공고 상세 조회")
def read_policy(
    pbanc_sn: int,
    db: Session = Depends(get_db),
):
    policy = get_policy(db=db, pbanc_sn=pbanc_sn)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy announcement not found")
    return policy
