from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud.policy import get_policy, list_policies
from app.schemas.policy import PolicyAnnouncementDetailRead, PolicyAnnouncementRead

router = APIRouter()


@router.get("/", response_model=list[PolicyAnnouncementRead], summary="정책 공고 목록 조회")
def read_policies(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    return list_policies(db=db, skip=skip, limit=limit)


@router.get("/{pbanc_sn}", response_model=PolicyAnnouncementDetailRead, summary="정책 공고 상세 조회")
def read_policy(
    pbanc_sn: int,
    db: Session = Depends(get_db),
):
    policy = get_policy(db=db, pbanc_sn=pbanc_sn)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy announcement not found")
    return policy
