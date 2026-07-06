from fastapi import APIRouter
from sqlalchemy.orm import Session
from fastapi import Depends
from app.core.database import get_db

# 담당: 김정연 (데이터 파이프라인 · 공고 조회)
# policies 테이블은 소진공 크롤링 + 행안부 OpenAPI 취합 결과의 단일 원천입니다.
router = APIRouter()


@router.get("/", summary="공고 목록 조회 (필터)")
def list_policies(
    category: str | None = None,
    region: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """
    공고 목록을 필터 조건으로 조회합니다.
    TODO(김정연): policies 테이블에서 category/region/status 필터 조회.
    """
    return {"items": []}


@router.get("/{policy_id}", summary="공고 상세 조회")
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    """
    단일 공고 상세를 조회합니다.
    TODO(김정연): policies 단건 조회.
    """
    return {"id": policy_id}
