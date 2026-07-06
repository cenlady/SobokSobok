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


# ── Google OAuth (담당: 이재혁 - 캘린더 연동용) ────────────────────────────
@router.get("/google", summary="Google OAuth 시작 (캘린더 연동)")
def google_login():
    """
    Google 계정 연결을 위한 OAuth 동의 화면으로 리다이렉트합니다.
    TODO(이재혁): Google OAuth authorize URL 로 redirect.
    """
    return {"message": "TODO: redirect to Google OAuth consent screen"}


@router.get("/google/callback", summary="Google OAuth 콜백 · 토큰 저장")
def google_callback(code: str | None = None):
    """
    OAuth 콜백을 받아 액세스/리프레시 토큰을 교환·저장합니다.
    TODO(이재혁): code → 토큰 교환 → 사용자별 저장.
    """
    return {"message": "TODO: exchange code and store token"}
