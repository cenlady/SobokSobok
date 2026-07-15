from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.model_provider import get_user_model_mode
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
from app.services.chat_rag import get_or_create_chat_session, record_recommendation_turn

router = APIRouter()


@router.post("/preview", response_model=RecommendationPreviewResponse, summary="프로필 기반 맞춤 정책 추천")
def preview_recommendations(
    profile: RecommendationProfileRequest,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=50),
    chat_session_id: UUID | None = Query(
        default=None,
        description="메인 채팅에서 추천을 요청한 경우 이어질 후속 질문을 위해 사용하는 채팅 세션 ID",
    ),
    source_query: str | None = Query(
        default=None,
        max_length=200,
        description="메인 채팅에서 추천을 요청한 원문. 값이 있으면 추천 결과를 채팅 이력에 저장한다.",
    ),
    status: list[Literal["all", "eligible", "needs_review", "near_match"]] = Query(
        default=["all"],
        description="추천 상태를 하나 이상 선택합니다. 반복 query parameter로 전달합니다.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    all_results, vector_used, total_candidates = recommend_policies(
        db=db,
        profile=profile,
        # 상태별 필터와 페이지네이션은 동일한 전체 순위에서 적용해야
        # 페이지를 넘겨도 추천 순서가 흔들리지 않는다.
        limit=1000,
        model_mode=get_user_model_mode(current_user, "recommendation"),
    )
    status_counts = {
        "eligible": sum(item.match_status == "eligible" for item in all_results),
        "needs_review": sum(item.match_status == "needs_review" for item in all_results),
        "near_match": sum(item.match_status == "near_match" for item in all_results),
    }
    selected_statuses = set(status)
    filtered_results = (
        all_results
        if not selected_statuses or "all" in selected_statuses
        else [item for item in all_results if item.match_status in selected_statuses]
    )
    results = filtered_results[skip : skip + limit]
    profile_warnings = profile_validation_warnings(profile)
    chat_session = None
    if source_query is not None or chat_session_id is not None:
        try:
            chat_session = get_or_create_chat_session(
                db,
                user_id=current_user.id,
                session_id=chat_session_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        profile_region = {
            "sido": profile.region.sido if profile.region else None,
            "sigungu": profile.region.sigungu if profile.region else None,
        }
        record_recommendation_turn(
            db,
            session=chat_session,
            profile_region=profile_region,
            results=results,
            source_query=source_query or "맞춤 정책 추천해줘",
            profile_warnings=profile_warnings,
        )
    return RecommendationPreviewResponse(
        chat_session_id=chat_session.id if chat_session else None,
        total_candidates=total_candidates,
        filtered_candidates=len(filtered_results),
        returned=len(results),
        skip=skip,
        limit=limit,
        has_next=skip + len(results) < len(filtered_results),
        status_counts=status_counts,
        vector_used=vector_used,
        profile_warnings=profile_warnings,
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
        return explain_policy_recommendation(
            db=db,
            policy_id=policy_id,
            profile=profile,
            model_mode=get_user_model_mode(current_user, "recommendation"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
