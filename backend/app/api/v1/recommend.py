from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.recommend import (
    RecommendationPreviewResponse,
    RecommendationProfileRequest,
    RecommendationExplanationResponse,
)
from app.services.recommend import (
    explain_policy_recommendation,
    profile_validation_warnings,
    recommend_policies,
)

router = APIRouter()


@router.post("/preview", response_model=RecommendationPreviewResponse, summary="프로필 기반 맞춤 정책 추천")
def preview_recommendations(
    profile: RecommendationProfileRequest,
    limit: int = Query(default=15, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results, vector_used, total_candidates = recommend_policies(
        db=db,
        profile=profile,
        limit=limit,
    )
    return RecommendationPreviewResponse(
        total_candidates=total_candidates,
        returned=len(results),
        vector_used=vector_used,
        profile_warnings=profile_validation_warnings(profile),
        results=results,
    )


@router.post(
    "/explain/{policy_id}",
    response_model=RecommendationExplanationResponse,
    summary="정책 추천 이유 자연어 설명 생성",
)
def explain_recommendation(
    policy_id: UUID,
    profile: RecommendationProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return explain_policy_recommendation(db=db, policy_id=policy_id, profile=profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
