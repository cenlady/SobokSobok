from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NumberRange(BaseModel):
    """수치 범위. max=None은 '제한 없음'을 뜻한다 (예: '10억 이상', '7년 이상')."""
    min: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def _check_order(self) -> "NumberRange":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min은 max보다 클 수 없습니다.")
        return self


class LabeledRange(NumberRange):
    """사용자가 고른 선택지의 라벨 + 그 라벨이 뜻하는 범위."""
    label: str | None = None


class LabeledTags(BaseModel):
    """사용자가 고른 선택지의 라벨 + 그 라벨이 뜻하는 태그들."""
    label: str | None = None
    tags: list[str] = Field(default_factory=list)


class RegionInput(BaseModel):
    sido: str | None = None
    sigungu: str | None = None


class ProfileUpsertRequest(BaseModel):
    """온보딩/마이페이지에서 프로필을 통째로 저장할 때 쓰는 요청 바디.

    프론트의 Profile 타입과 모양을 맞춰, 라벨(표시용)과 태그·범위(추천 계산용)를 함께 받는다.
    """
    owner_name: str | None = None
    store_name: str | None = None
    region: RegionInput | None = None

    industry: LabeledTags = Field(default_factory=LabeledTags)
    business_status: LabeledTags = Field(default_factory=LabeledTags)

    annual_sales: LabeledRange = Field(default_factory=LabeledRange)
    employees: LabeledRange = Field(default_factory=LabeledRange)
    business_age: LabeledRange = Field(default_factory=LabeledRange)

    need_tags: list[str] = Field(default_factory=list)


class ProfileResponse(ProfileUpsertRequest):
    """저장된 프로필. onboarded_at이 None이면 프론트는 사용자를 온보딩으로 보낸다."""
    onboarded_at: datetime | None = None


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    onboarded: bool = Field(..., description="온보딩 완료 여부 (False면 /onboarding으로 보낼 것)")


class FavoriteCreateRequest(BaseModel):
    policy_id: UUID


class FavoriteItem(BaseModel):
    """저장한 정책 1건. 정책 내용은 스냅샷이 아니라 조인해서 항상 최신을 내려준다."""
    policy_id: UUID
    title: str
    summary: str | None = None
    organization: str | None = None
    support_type: str | None = None
    apply_start: datetime | None = None
    apply_end: datetime | None = None
    apply_url: str | None = None
    saved_at: datetime
