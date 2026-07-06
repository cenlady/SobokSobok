from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db

# 담당: 김정연 (챗봇 · LLM + RAG)
# 검색 corpus: policies.body → chat_vectors (자기 임베딩 모델)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list | None = None


@router.post("/", summary="챗봇 대화 (LLM + RAG)")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    사용자 질문에 대해 공고를 검색(RAG)해 응답하고, 관련 정책 카드를 함께 반환합니다.
    TODO(김정연): chat_vectors 검색 → LLM 응답 생성 → benefit_ids 첨부.
    """
    return {"reply": "", "benefit_ids": []}
