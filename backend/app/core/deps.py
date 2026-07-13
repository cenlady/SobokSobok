# -*- coding: utf-8 -*-
# 파일 역할: [공통/인증 도메인] FastAPI 의존성 — 요청의 JWT를 검증해 현재 사용자를 해석한다.

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# auto_error=False: 헤더가 없을 때 FastAPI가 먼저 403을 던지지 않게 하고,
# 우리가 일관되게 401 + WWW-Authenticate를 내려준다.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="인증이 필요합니다. 구글 로그인 후 다시 시도해주세요.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authorization: Bearer <JWT> 를 검증해 User를 반환한다.

    토큰이 없거나/만료/위조이거나, 토큰의 subject에 해당하는 사용자가 없거나
    비활성 계정이면 401. 라우터는 이 의존성만 걸면 인증된 사용자를 보장받는다.
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    email = decode_access_token(credentials.credentials)
    if email is None:
        raise _UNAUTHORIZED

    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or not user.is_active:
        raise _UNAUTHORIZED

    return user
