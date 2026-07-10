# -*- coding: utf-8 -*-
# 파일 역할: [인증 도메인] 사용자 기본 로그인 및 Google OAuth 2.0 소셜 로그인 인증 처리 라우터

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from google_auth_oauthlib.flow import Flow
from app.core.config import settings

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

@router.get("/google/login-url", summary="Google 로그인 URL 요청")
def get_google_login_url():
    """
    [이재혁 - 인증 영역]
    - 프론트엔드가 '구글 로그인' 버튼을 눌렀을 때 이동할 구글 동의 페이지 리다이렉트 URL을 반환합니다.
    - 구글 캘린더 연동을 위해 'https://www.googleapis.com/auth/calendar' 권한 스코프를 필수 포함해야 합니다.
    """
    # Google OAuth API 자격증명 구성 여부 검증 (누락 시 명시적 오류 가이드)
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are not configured. Please set them in your .env file."
        )

    # 1) 구글 API 연동 권한 범위 지정
    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/calendar"  # 구글 캘린더 읽기/쓰기 스코프
    ]

    # 2) 클라이언트 설정 조립
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    try:
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=scopes,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )

        # 3) 구글 로그인 동의 페이지 리다이렉트 URL 생성
        # - access_type="offline" -> 백그라운드 캘린더 연동을 위해 Refresh Token을 필수로 구글에 요구함
        # - prompt="consent" -> 로그인할 때마다 동의 절차를 띄워 구글이 항상 Refresh Token을 무결하게 내려주도록 유도함
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true"
        )

        return {
            "login_url": authorization_url,
            "state": state
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Google authorization URL: {e}"
        )

@router.get("/google/callback", summary="Google 로그인 콜백 수신")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    [이재혁 - 인증 영역]
    - 사용자가 구글 승인을 마친 후 구글 서버가 보내주는 인증 코드(code)를 수신합니다.
    - 수신한 code를 구글 토큰 서버로 보내 Access/Refresh Token을 획득하고, users 테이블에 저장한 후 로컬 JWT 토큰을 발행합니다.
    """
    return {
        "message": "Google Authorization Code received successfully",
        "code": code
    }
