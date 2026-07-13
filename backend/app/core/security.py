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


def decode_access_token(token: str) -> str | None:
    """JWT를 검증하고 subject(이메일)를 돌려준다. 만료·위조·형식 오류는 모두 None.

    호출부(get_current_user)가 None을 401로 변환한다. 여기서 예외를 던지지 않는 이유는
    "왜 실패했는지"를 클라이언트에 흘리지 않기 위해서다(만료/위조 구분은 공격자에게만 유용).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
