# -*- coding: utf-8 -*-
# 파일 역할: [공통] API 요청에서 구글 Access Token 검증 및 로그인 유저 주입용 의존성 정의

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# HTTPBearer를 사용하면 Swagger UI에 오직 Value 입력란 단 하나만 직관적으로 노출됩니다.
security_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme), db: Session = Depends(get_db)) -> User:
    """
    [이재혁 - 인증/캘린더 영역]
    - HTTP Header로 실려온 구글 Access Token을 검증하여 현재 로그인된 유저 객체(User)를 반환합니다.
    - 성능 최적화를 위해 매번 구글 서버에 통신하지 않고, 우리 DB에 등록된 유효 토큰 및 만료 시각(google_token_expires_at)을 먼저 1차 검사(캐싱)합니다.
    - 만약 캐시 만료 등으로 DB 대조가 실패할 경우에만, 구글 공식 토큰정보 검증 API를 호출해 교차 검증합니다.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Google Access Token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    now = datetime.now(timezone.utc)

    # 1) 성능 최적화: 우리 DB에서 해당 구글 토큰을 갖고 있고, 아직 만료되지 않은 유저가 있는지 먼저 체크 (0ms)
    user = (
        db.query(User)
        .filter(User.google_access_token == token)
        .filter(User.google_token_expires_at > now)
        .first()
    )
    if user:
        return user

    # 2) DB 캐시 실패 시: 구글 검증 서버(tokeninfo)에 직접 물어보아 만료 여부 및 이메일 확인 (구글 연계 통신)
    try:
        response = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": token},
            timeout=5.0
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google Access Token or session expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        token_info = response.json()
        user_email = token_info.get("email")
        expires_in = int(token_info.get("expires_in", 0))  # 남은 수명(초 단위)

        if not user_email:
            raise ValueError("Email not found in Google Token Info response.")

        # 3) 구글 인증 통과 시, 이메일로 유저를 조회해 최신 토큰 정보를 DB에 동기화 캐싱
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User registered via Google not found in our database."
            )

        # 최신 토큰 정보로 DB 업데이트 (다음 호출 시 빠른 통과를 보장)
        user.google_access_token = token
        user.google_token_expires_at = now + timedelta(seconds=expires_in)
        db.commit()

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google Token validation failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
