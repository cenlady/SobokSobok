from __future__ import annotations

from pydantic import BaseModel, Field


class RequirementMatch(BaseModel):
    """정책 요건 하나에 대한 업로드 서류의 커버 여부 (RAG 임베딩 대조 근거)."""
    document_name: str = Field(..., description="정책이 요구하는 서류명")
    best_similarity: float = Field(..., description="업로드 청크 중 최고 유사도")
    likely_covered: bool = Field(..., description="후보 임계값 이상이면 True (최종 판정은 LLM)")


class ReviewResult(BaseModel):
    """서류 검토 진단 결과 (자체 검토 + 정책 요건 대조)."""
    document_type: str = Field(..., description="업로드 서류로 추정되는 유형")
    # 서류 자체 검토
    typos: list[str] = Field(default_factory=list, description="오타·맞춤법 오류")
    missing_fields: list[str] = Field(default_factory=list, description="비어 있거나 빠진 항목·칸")
    format_issues: list[str] = Field(default_factory=list, description="형식·양식상의 오류")
    # 정책 요건 대조 (policy_id가 주어진 경우)
    missing_documents: list[str] = Field(default_factory=list, description="정책 요구 서류 중 누락된 것")
    improvement_points: list[str] = Field(default_factory=list, description="보완이 필요한 점")
    overall: str = Field(..., description="종합 진단 요약")


class ReviewStartResponse(BaseModel):
    """검토 접수 응답. 검토는 백그라운드에서 돌고, 이 id로 진행 상태를 폴링한다."""
    upload_id: str
    policy_id: str | None = Field(None, description="요건 대조에 사용할 정책 (선택)")
    review_status: str = Field(..., description="검토 진행 단계 (접수 직후에는 queued)")
    has_requirement_matching: bool = Field(
        ..., description="policy_id가 있어 요건 대조 단계를 거치는지 (프론트 진행 단계 수 결정용)"
    )


class ReviewResponse(BaseModel):
    upload_id: str
    policy_id: str | None = Field(None, description="요건 대조에 사용한 정책 (선택)")
    review_status: str = Field(
        ..., description="검토 진행 단계 (queued/extracting/matching/diagnosing/done/failed)"
    )
    extraction_status: str = Field(..., description="업로드 서류 텍스트 추출 상태 (실패 사유)")
    requirement_matches: list[RequirementMatch] = Field(
        default_factory=list, description="요건별 임베딩 대조 근거 (policy_id가 있을 때)"
    )
    result: ReviewResult | None = Field(
        None, description="진단 결과. 아직 진행 중(done/failed 이전)이면 null"
    )
