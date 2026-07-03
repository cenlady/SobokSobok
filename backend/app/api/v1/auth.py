from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db

router = APIRouter()

@router.post("/login", summary="로그인 엔드포인트")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    사용자 로그인을 위한 임시 엔드포인트입니다.
    """
    # 임시 인증 로직 구현
    if form_data.username == "admin" and form_data.password == "admin123":
        return {
            "access_token": "mock-jwt-token-for-development",
            "token_type": "bearer"
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("/test-auth", summary="인증 테스트용 임시 엔드포인트")
def test_auth():
    return {"message": "인증 라우터 정상 작동 중"}
