from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db

# 담당: 이재혁 (Google Calendar MCP · 아키텍처)
# 서류 준비 스케줄 코치: required_documents → prep_vectors RAG(소요기간·팁)
#   → 사용자 가용시간(선호 + Google Calendar busy) 배분 → Calendar MCP 이벤트 생성
router = APIRouter()


class ScheduleRequest(BaseModel):
    policy_id: str


@router.post("/schedule", summary="서류 준비 스케줄 코치 → Google Calendar 등록")
def schedule(req: ScheduleRequest, db: Session = Depends(get_db)):
    """
    정책의 제출서류를 준비 일정으로 나눠 사용자 Google Calendar에 등록합니다.
    TODO(이재혁): required_documents → prep_vectors RAG(소요기간·팁) →
      가용시간 배분 → Google Calendar MCP 로 서류별 이벤트 생성.
    """
    return {"schedule": []}
