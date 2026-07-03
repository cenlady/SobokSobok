from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db

router = APIRouter()

@router.get("/", summary="사용자 목록 조회 임시 엔드포인트")
def read_users(db: Session = Depends(get_db)):
    """
    사용자 목록 조회를 위한 임시 엔드포인트입니다.
    """
    # 임시 Mock 데이터 리턴
    return [
        {"id": 1, "username": "user1", "email": "user1@example.com"},
        {"id": 2, "username": "user2", "email": "user2@example.com"}
    ]

@router.get("/me", summary="내 정보 조회 임시 엔드포인트")
def read_user_me():
    return {"id": 999, "username": "current_user", "email": "me@example.com"}
