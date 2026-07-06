from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db

# 담당: 안주현 (정책 추천 · 배포)
# RAG 하이브리드: eligibility 구조화 필드 사전필터 → rec_vectors 벡터 유사도 재정렬
router = APIRouter()


class RecommendRequest(BaseModel):
    profile: dict | None = None  # 없으면 저장된 사용자 프로필 사용
    top_k: int = 5


@router.post("/", summary="정책 추천 (프로필 기반 RAG 하이브리드)")
def recommend(req: RecommendRequest, db: Session = Depends(get_db)):
    """
    사용자 프로필(업종/지역/매출/직원수)에 맞는 정책을 추천합니다.
    TODO(안주현): eligibility 구조화 사전필터 → rec_vectors 재정렬 → top_k 반환.
    """
    return {"items": []}
