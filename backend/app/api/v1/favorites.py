from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.normalized_policy import NormalizedPolicy
from app.models.user import Favorite, User
from app.schemas.user import FavoriteCreateRequest, FavoriteItem
from app.services.recommend import classify_need_tags

router = APIRouter()


@router.get("", response_model=list[FavoriteItem], summary="내가 저장한 정책 목록")
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """저장한 정책을 최근 저장순으로 반환한다.

    정책 내용을 스냅샷으로 복사해두지 않고 매번 조인한다 — 정책이 갱신되면
    (마감일 연장 등) 저장 목록과 홈 달력도 함께 최신이어야 하기 때문.
    """
    rows = (
        db.query(Favorite, NormalizedPolicy)
        .join(NormalizedPolicy, NormalizedPolicy.id == Favorite.policy_id)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return [
        FavoriteItem(
            policy_id=policy.id,
            title=policy.title,
            summary=policy.summary,
            organization=policy.organization,
            support_type=policy.support_type,
            region_scope=policy.region_scope,
            sido=policy.sido,
            sigungu=policy.sigungu,
            status=policy.status,
            apply_start=policy.apply_start,
            apply_end=policy.apply_end,
            apply_url=policy.apply_url,
            saved_at=favorite.created_at,
            categories=classify_need_tags(policy),
        )
        for favorite, policy in rows
    ]


@router.post("", response_model=FavoriteItem, status_code=status.HTTP_201_CREATED, summary="정책 저장")
def add_favorite(
    payload: FavoriteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = db.get(NormalizedPolicy, payload.policy_id)
    if policy is None or not policy.is_active:
        raise HTTPException(status_code=404, detail="해당 정책을 찾을 수 없습니다.")

    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.policy_id == payload.policy_id)
        .one_or_none()
    )
    # 이미 저장돼 있으면 그대로 돌려준다. 저장 버튼 연타나 재시도가 409로 깨지지 않도록 멱등하게.
    favorite = existing or Favorite(user_id=current_user.id, policy_id=payload.policy_id)
    if existing is None:
        db.add(favorite)
        db.commit()
        db.refresh(favorite)

    return FavoriteItem(
        policy_id=policy.id,
        title=policy.title,
        summary=policy.summary,
        organization=policy.organization,
        support_type=policy.support_type,
        region_scope=policy.region_scope,
        sido=policy.sido,
        sigungu=policy.sigungu,
        status=policy.status,
        apply_start=policy.apply_start,
        apply_end=policy.apply_end,
        apply_url=policy.apply_url,
        saved_at=favorite.created_at,
        categories=classify_need_tags(policy),
    )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT, summary="정책 저장 해제")
def remove_favorite(
    policy_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.policy_id == policy_id)
        .delete()
    )
    db.commit()
    # 없던 것을 지워도 성공으로 본다(멱등). 저장 해제는 "없는 상태"가 목표이지
    # "무언가를 지우는 것"이 목표가 아니다.
    _ = deleted
    return Response(status_code=status.HTTP_204_NO_CONTENT)
