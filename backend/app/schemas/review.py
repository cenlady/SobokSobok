from __future__ import annotations

from pydantic import BaseModel, Field


class RequirementMatch(BaseModel):
    """정책 요건 하나에 대한 업로드 서류의 커버 여부(임베딩 후보 판정)."""
    document_name: str = Field(..., description="정책이 요구하는 서류명")
    best_similarity: float = Field(..., description="업로드 청크 중 최고 유사도")
    likely_covered: bool = Field(..., description="후보 임계값 이상이면 True (최종 판정은 LLM)")


class ReviewResult(BaseModel):
    """파일 검토 진단 결과 (이슈 #6 응답 스키마)."""
    document_type: str = Field(..., description="업로드 서류로 추정되는 유형")
    missing_items: list[str] = Field(default_factory=list, description="누락된 요건/서류")
    improvement_points: list[str] = Field(default_factory=list, description="보완이 필요한 점")
    overall: str = Field(..., description="종합 진단 요약")


class ReviewResponse(BaseModel):
    upload_id: str
    policy_id: str
    extraction_status: str = Field(..., description="업로드 서류 텍스트 추출 상태")
    requirement_matches: list[RequirementMatch] = Field(
        default_factory=list, description="요건별 임베딩 대조 결과(진단 보조 근거)"
    )
    result: ReviewResult
