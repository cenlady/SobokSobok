from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegionInput(BaseModel):
    sido: str | None = None
    sigungu: str | None = None


class NumberRangeInput(BaseModel):
    min: int | None = None
    max: int | None = None


class RecommendationProfileRequest(BaseModel):
    region: RegionInput | None = None
    industry_tags: list[str] = Field(default_factory=list)
    business_status_tags: list[str] = Field(default_factory=list)
    employees: NumberRangeInput | int | None = None
    annual_sales_krw: NumberRangeInput | int | None = None
    business_age_years: NumberRangeInput | int | None = None
    need_tags: list[str] = Field(default_factory=list)
    use_vectors: bool = True


class RecommendationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: UUID
    title: str
    summary: str | None = None
    organization: str | None = None
    support_type: str | None = None
    support_content: str | None = None
    apply_url: str | None = None
    apply_start: datetime | None = None
    apply_end: datetime | None = None
    # 프론트가 '상시 접수'(open + 마감일 없음)와 '기간 확인 필요'(notice)를 가르는 데 쓴다.
    # 이게 없으면 마감일 없는 정책이 전부 '기간 미상'으로 보인다.
    status: str | None = None
    match_status: Literal["eligible", "needs_review", "near_match"]
    confidence: Literal["high", "medium", "low"]
    rank_score: float
    vector_similarity: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unknown_conditions: list[str] = Field(default_factory=list)
    unmet_conditions: list[str] = Field(default_factory=list)
    matched_tags: dict[str, list[str]] = Field(default_factory=dict)


class RecommendationPreviewResponse(BaseModel):
    total_candidates: int
    returned: int
    vector_used: bool
    results: list[RecommendationResult]


class RecommendationExplanationResponse(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    aspects_to_check: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
