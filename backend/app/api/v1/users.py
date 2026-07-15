from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserProfile
from app.schemas.user import (
    LabeledRange,
    LabeledTags,
    ProfileResponse,
    ProfileUpsertRequest,
    RegionInput,
    UserMeResponse,
)

router = APIRouter()


@router.get("/me", response_model=UserMeResponse, summary="내 계정 정보")
def read_user_me(current_user: User = Depends(get_current_user)):
    profile = current_user.profile
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        onboarded=bool(profile and profile.onboarded_at),
    )


@router.get("/me/profile", response_model=ProfileResponse, summary="내 프로필 조회")
def read_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_response(_get_or_create_profile(db, current_user))


@router.put("/me/profile", response_model=ProfileResponse, summary="내 프로필 저장 (온보딩/마이페이지)")
def upsert_my_profile(
    payload: ProfileUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """프로필을 통째로 덮어쓰고, 최초 저장이면 온보딩 완료로 표시한다.

    부분 수정(PATCH)이 아니라 전체 교체(PUT)인 이유: 온보딩과 마이페이지 모두 전체 폼을
    제출하는 화면이라, 부분 수정을 지원하면 "빈 값으로 지움"과 "건드리지 않음"을
    구분해야 해서 프론트·백엔드가 함께 복잡해진다.
    """
    profile = _get_or_create_profile(db, current_user)

    profile.owner_name = payload.owner_name
    profile.store_name = payload.store_name
    profile.chat_model_mode = payload.chat_model_mode
    profile.recommend_model_mode = payload.recommend_model_mode
    profile.policy_summary_model_mode = payload.policy_summary_model_mode
    profile.calendar_coach_model_mode = payload.calendar_coach_model_mode
    profile.document_review_model_mode = payload.document_review_model_mode

    region = payload.region or RegionInput()
    profile.region_sido = region.sido
    profile.region_sigungu = region.sigungu

    profile.industry_tags = payload.industry.tags
    profile.industry_label = payload.industry.label
    profile.business_status_tags = payload.business_status.tags
    profile.business_status_label = payload.business_status.label
    profile.need_tags = payload.need_tags

    profile.annual_sales_min = payload.annual_sales.min
    profile.annual_sales_max = payload.annual_sales.max
    profile.annual_sales_label = payload.annual_sales.label

    profile.employees_min = payload.employees.min
    profile.employees_max = payload.employees.max
    profile.employees_label = payload.employees.label

    profile.business_age_min = payload.business_age.min
    profile.business_age_max = payload.business_age.max
    profile.business_age_label = payload.business_age.label

    # 최초 저장 시점만 온보딩 완료로 본다. 이후 마이페이지 수정으로는 갱신하지 않는다.
    if profile.onboarded_at is None:
        profile.onboarded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)
    return _to_response(profile)


def _get_or_create_profile(db: Session, user: User) -> UserProfile:
    """프로필 행을 보장한다. 구글 콜백이 만들어 두지만, 그 이전 가입자에 대한 방어."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _to_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        owner_name=profile.owner_name,
        store_name=profile.store_name,
        chat_model_mode=profile.chat_model_mode or "cloud",
        recommend_model_mode=profile.recommend_model_mode or "cloud",
        policy_summary_model_mode=profile.policy_summary_model_mode or "cloud",
        calendar_coach_model_mode=profile.calendar_coach_model_mode or "cloud",
        document_review_model_mode=profile.document_review_model_mode or "local",
        region=RegionInput(sido=profile.region_sido, sigungu=profile.region_sigungu),
        industry=LabeledTags(
            label=profile.industry_label,
            tags=list(profile.industry_tags or []),
        ),
        business_status=LabeledTags(
            label=profile.business_status_label,
            tags=list(profile.business_status_tags or []),
        ),
        annual_sales=LabeledRange(
            label=profile.annual_sales_label,
            min=profile.annual_sales_min,
            max=profile.annual_sales_max,
        ),
        employees=LabeledRange(
            label=profile.employees_label,
            min=profile.employees_min,
            max=profile.employees_max,
        ),
        business_age=LabeledRange(
            label=profile.business_age_label,
            min=profile.business_age_min,
            max=profile.business_age_max,
        ),
        need_tags=list(profile.need_tags or []),
        onboarded_at=profile.onboarded_at,
    )
