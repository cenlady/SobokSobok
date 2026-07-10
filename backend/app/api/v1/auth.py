# -*- coding: utf-8 -*-
# 파일 역할: [인증 도메인] 사용자 기본 로그인 및 Google OAuth 2.0 소셜 로그인 인증 처리 라우터

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from google_auth_oauthlib.flow import Flow
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User, UserProfile
import httpx
from datetime import datetime, timezone

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
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are not configured. Please set them in your .env file."
        )

    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/calendar"
    ]

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
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are not configured."
        )

    # 1) 인증 코드로 구글 토큰 교환을 위한 Flow 설정
    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/calendar"
    ]
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
        # 구글 서버와 통신하여 Token 교환 수행
        flow.fetch_token(code=code)
        credentials = flow.credentials
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange authorization code for Google token: {e}"
        )

    # 2) 획득한 Access Token을 사용하여 구글 유저 정보(이메일) 획득
    try:
        headers = {"Authorization": f"Bearer {credentials.token}"}
        userinfo_response = httpx.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()
        user_email = user_info.get("email")
        if not user_email:
            raise ValueError("Email not found in Google userinfo response.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve user profile from Google: {e}"
        )

    # 3) DB에서 유저 조회 및 자동 회원가입
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        # 신규 유저 생성
        user = User(
            email=user_email,
            hashed_password=None,  # 소셜 로그인이므로 비밀번호 없음
            is_active=True
        )
        db.add(user)
        db.flush()  # ID 발급을 위해 DB 반영

        # 신규 유저 프로필 자동 생성
        profile = UserProfile(
            user_id=user.id,
            industry=[],
            region="",
            sales=0,
            employees=0,
            available_time_preference={}
        )
        db.add(profile)

    # 4) 구글 연동 토큰 정보 DB 업데이트
    user.google_access_token = credentials.token
    
    # Refresh Token은 최초 승인 시에만 발급되므로, 새로 발급되었을 때만 덮어씀 (기존 저장값 보존)
    if credentials.refresh_token:
        user.google_refresh_token = credentials.refresh_token
        
    # 만료시간 타임존 보정 (UTC timezone-aware 형식)
    if credentials.expiry:
        user.google_token_expires_at = credentials.expiry.replace(tzinfo=timezone.utc)

    db.commit()

    # 5) 우리 백엔드 세션용 자체 로그인 JWT 토큰 발행
    local_access_token = create_access_token(subject=user.email)

    return {
        "access_token": local_access_token,
        "token_type": "bearer",
        "email": user.email
    }
