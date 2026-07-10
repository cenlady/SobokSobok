# -*- coding: utf-8 -*-
# 파일 역할: [공통/인증 도메인] 보안 유틸리티 (JWT 토큰 발행 및 비밀번호 해싱 등)

import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from app.core.config import settings

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    [공통/인증 영역]
    - 사용자 식별 정보(예: 이메일)를 담아 암호화된 JWT Access Token을 발행합니다.
    - 만료 시간(settings.ACCESS_TOKEN_EXPIRE_MINUTES)이 경과하면 토큰은 유효하지 않게 됩니다.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode = {
        "exp": expire,
        "sub": str(subject)
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt
