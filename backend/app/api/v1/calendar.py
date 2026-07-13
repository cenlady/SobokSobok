# -*- coding: utf-8 -*-
# 파일 역할: [일정 관리 도메인] 구글 캘린더 API 연동 및 일정 마감일 자동 등록 라우터

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, UUID4
import httpx
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.normalized_policy import NormalizedPolicy
from app.core.config import settings

router = APIRouter()

# 캘린더 등록 요청용 Pydantic 스키마
class CalendarEventRequest(BaseModel):
    policy_id: UUID4

async def get_valid_google_token(user: User, db: Session) -> str:
    """
    사용자의 구글 액세스 토큰의 유효성을 검사하고, 
    만료되었거나 임박한 경우 Refresh Token을 사용해 자동으로 토큰을 갱신합니다.
    """
    now = datetime.now(timezone.utc)
    
    # 1) 만료 시점(expires_at)이 5분 이상 넉넉히 남았다면 기존 토큰 그대로 반환
    if user.google_access_token and user.google_token_expires_at:
        # DB 컬럼이 timezone-aware 일 테지만 혹시 모를 naive 대조 방지
        expires_at = user.google_token_expires_at.replace(tzinfo=timezone.utc)
        if expires_at > (now + timedelta(minutes=5)):
            return user.google_access_token

    # 2) 토큰이 없거나 만료 임박 시, Refresh Token을 사용해 갱신 시도
    if not user.google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Refresh Token is missing. Please log in again and accept Google Calendar permissions."
        )

    # 3) 구글 OAuth 토큰 갱신 API 호출
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": user.google_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to refresh Google Access Token. Google rejected the refresh request."
                )
            
            token_data = response.json()
            new_access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)

            # DB에 최신 토큰 및 만료 일시 캐싱
            user.google_access_token = new_access_token
            user.google_token_expires_at = now + timedelta(seconds=expires_in)
            db.commit()

            return new_access_token
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Google Token refresh connection error: {e}"
            )

@router.post("/event", summary="구글 캘린더 일정 등록")
async def register_policy_calendar_event(
    payload: CalendarEventRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - 캘린더 영역]
    - 특정 지원사업 ID(policy_id)를 입력받아 마감 일정을 사용자의 구글 달력에 등록해 줍니다.
    - 구글 액세스 토큰 만료 시 Refresh Token으로 자동 무중단 갱신을 지원합니다.
    """
    # 1) 대상 정책(지원금 공고) 조회
    policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == payload.policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target policy document not found."
        )

    # 2) 신청 마감일 컬럼 존재 여부 체크
    if not policy.apply_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This policy does not have a deadline (apply_end) date, so it cannot be added to the calendar."
        )

    # 3) 유효한 구글 토큰 확보 (필요 시 오토 리프레시 작동)
    access_token = await get_valid_google_token(current_user, db)

    # 4) 구글 캘린더 종일 일정(All-day Event) 리소스 구성
    # 구글 API 스펙상 종일 일정의 end 날짜는 exclusive(미만)이므로, 하루짜리 종일은 마감일 + 1일로 설정해야 마감일 당일 하루로 등록됩니다.
    start_date_str = policy.apply_end.strftime("%Y-%m-%d")
    end_date = policy.apply_end + timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")

    event_body = {
        "summary": f"[소복소복] {policy.title} 신청 마감",
        "description": (
            f"● 지원사업명: {policy.title}\n"
            f"● 소관기관: {policy.organization or '확인불가'}\n"
            f"● 온라인 신청 주소: {policy.apply_url or '외부 링크가 명시되지 않음'}\n\n"
            f"* 본 일정은 소복소복 AI RAG 시스템에 의해 사장님의 캘린더에 연동된 자동 관리 일정입니다."
        ),
        "start": {
            "date": start_date_str
        },
        "end": {
            "date": end_date_str
        },
        "reminders": {
            "useDefault": True
        }
    }

    # 5) 구글 캘린더 API 호출 (이벤트 생성)
    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                json=event_body,
                headers=headers,
                timeout=10.0
            )
            if response.status_code != 200:
                # 구글이 에러 코드를 뱉을 시 (예: 토큰 만료 또는 권한 미달)
                error_detail = response.json().get("error", {}).get("message", "Google Calendar API error")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Google Calendar Registration Failed: {error_detail}"
                )

            result = response.json()
            return {
                "message": "Policy deadline successfully registered to Google Calendar",
                "google_event_id": result.get("id"),
                "html_link": result.get("htmlLink")
            }
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to Google Calendar API: {e}"
            )
