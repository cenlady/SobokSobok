from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    """서류 자체 검토 진단 결과 (오타·빈칸·형식)."""
    document_type: str = Field(..., description="업로드 서류로 추정되는 유형")
    typos: list[str] = Field(default_factory=list, description="오타·맞춤법 오류 (원문 → 제안)")
    missing_fields: list[str] = Field(default_factory=list, description="비어 있거나 빠진 항목·칸")
    format_issues: list[str] = Field(default_factory=list, description="형식·양식상의 오류")
    improvement_points: list[str] = Field(default_factory=list, description="보완이 필요한 점")
    overall: str = Field(..., description="종합 진단 요약")


class ReviewResponse(BaseModel):
    upload_id: str
    policy_id: str | None = Field(None, description="맥락으로 참고한 정책 (선택)")
    extraction_status: str = Field(..., description="업로드 서류 텍스트 추출 상태")
    result: ReviewResult
