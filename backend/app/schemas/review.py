from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReviewStatus = Literal["queued", "extracting", "matching", "diagnosing", "done", "failed"]

RequirementStatus = Literal[
    "not_requested",  # 정책을 고르지 않았다
    "no_requirement_data",  # 정책은 골랐지만 공고에 필수서류가 명시돼 있지 않다
    "matched",  # 실제로 대조했다
]


class RequirementMatch(BaseModel):
    """정책 요건 하나에 대한 커버 여부 (올린 서류 전체 기준)."""

    document_name: str = Field(..., description="정책이 요구하는 서류명")
    best_similarity: float = Field(..., description="올린 서류들 중 최고 유사도")
    likely_covered: bool = Field(
        ..., description="후보 임계값 이상이면 True. 확정이 아니라 후보다"
    )
    matched_file: str | None = Field(
        None, description="이 요건을 커버하는 것으로 보이는 파일명 (covered일 때만)"
    )


class FileDiagnosis(BaseModel):
    """파일 하나의 자체 검토 결과. 요건 대조는 여기 없다 — 그건 세션 전체 기준이다."""

    document_type: str = Field(..., description="서류로 추정되는 유형")
    typos: list[str] = Field(default_factory=list, description="오타·맞춤법")
    missing_fields: list[str] = Field(default_factory=list, description="이 서류 안의 빈칸")
    format_issues: list[str] = Field(default_factory=list, description="형식·양식 오류")
    improvement_points: list[str] = Field(default_factory=list, description="보완이 필요한 점")
    overall: str = Field(..., description="이 서류에 대한 진단 한두 문장")


class ReviewFile(BaseModel):
    upload_id: str
    file_name: str | None = None
    extraction_status: str = Field(
        ..., description="읽기 결과·실패 사유 (pending/success/empty/unsupported/failed)"
    )
    diagnosis: FileDiagnosis | None = Field(
        None, description="아직 진단 전이거나 읽기에 실패했으면 null"
    )


class ReviewStartResponse(BaseModel):
    """검토 접수 응답. 검토는 백그라운드에서 돌고, 이 id로 진행 상태를 폴링한다."""

    session_id: str
    policy_id: str | None = None
    review_status: ReviewStatus
    file_count: int
    has_requirement_matching: bool = Field(
        ...,
        description="요건 대조 단계를 거치는지 (프론트 진행 단계 수 결정용). "
        "정책을 골랐어도 그 정책에 필수서류 정보가 없으면 False다.",
    )


class ReviewResponse(BaseModel):
    session_id: str
    policy_id: str | None = None
    review_status: ReviewStatus

    requirement_status: RequirementStatus = Field(
        ...,
        description="요건 대조를 '할 수 있었는지'. requirement_matches가 비었다고 해서 "
        "요건을 다 충족한 것이 아니다 — 애초에 요건 정보가 없었을 수 있다.",
    )
    requirement_matches: list[RequirementMatch] = Field(default_factory=list)

    files: list[ReviewFile] = Field(default_factory=list)
    summary: str | None = Field(None, description="세션 종합 진단. 진행 중이면 null")

    created_at: datetime | None = None
