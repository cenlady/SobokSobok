# -*- coding: utf-8 -*-
# 파일 역할: [일정 관리 도메인] 구글 캘린더 API 연동 및 RAG 기반 AI 코칭 일정 관리 라우터

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, UUID4
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import os

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.normalized_policy import NormalizedPolicy
from app.models.chat import PolicyChunk
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
    
    if user.google_access_token and user.google_token_expires_at:
        expires_at = user.google_token_expires_at.replace(tzinfo=timezone.utc)
        if expires_at > (now + timedelta(minutes=5)):
            return user.google_access_token

    if not user.google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Refresh Token is missing. Please log in again and accept Google Calendar permissions."
        )

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

async def get_google_calendar_events(access_token: str) -> List[str]:
    """
    구글 캘린더 API를 찔러 사용자의 향후 2주일간의 개인 일정을 조회합니다. (MCP Tool 역할 래퍼)
    """
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=14)).isoformat()
    
    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 10
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=5.0)
            if response.status_code != 200:
                return []
            
            items = response.json().get("items", [])
            schedules = []
            for item in items:
                summary = item.get("summary", "이름 없음")
                start_date = item.get("start", {}).get("date") or item.get("start", {}).get("dateTime", "")
                if start_date:
                    short_date = start_date[:10]  # YYYY-MM-DD
                    schedules.append(f"{short_date}: {summary}")
            return schedules
        except Exception:
            return []

@router.post("/event", summary="구글 캘린더 일정 등록")
async def register_policy_calendar_event(
    payload: CalendarEventRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - 캘린더 영역]
    - 특정 지원사업 ID(policy_id)를 입력받아 마감 일정을 사용자의 구글 달력에 등록해 줍니다.
    """
    policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == payload.policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target policy document not found."
        )

    if not policy.apply_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This policy does not have a deadline (apply_end) date, so it cannot be added to the calendar."
        )

    access_token = await get_valid_google_token(current_user, db)

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

@router.get("/coach", summary="RAG 일정 관리 AI 가이드 코치 스케줄러")
async def get_calendar_coach_timeline(
    policy_id: UUID4,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - RAG AI 코칭 영역]
    - RAG 지식(공고 필수 서류 및 우대조건)과 사용자의 실제 구글 일정(MCP 연동)을 융합하여,
      바쁜 개인 일정을 피해 접수를 완수하도록 돕는 D-Day별 초개인화 AI 코칭 타임라인을 제공합니다.
    """
    # -------------------------------------------------------------
    # [이재혁 사장님 전용 - AI 코치 LLM 제공자 스위치 설정]
    # - "gemini": Google Gemini 모델을 사용해 코칭 텍스트를 생성합니다.
    # - "openai": 유료 상용 모델(gpt-4o-mini)을 사용하여 고품질 완성형 비서 텍스트를 기동합니다.
    # - "ollama": 로컬 본체에 켜진 무료 한국어 모델(exaone3.5)을 사용해 100% 무료로 기동합니다.
    # ➔ CHAT_COMPLETION_PROVIDER 설정을 따라갑니다.
    # -------------------------------------------------------------
    COACH_LLM_PROVIDER = settings.CHAT_COMPLETION_PROVIDER.lower()

    # 1) 지원사업 조회 및 기본 검사
    policy = db.query(NormalizedPolicy).filter(NormalizedPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target policy document not found."
        )

    if not policy.apply_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This policy does not have a deadline (apply_end) date, so coaching cannot be generated."
        )

    # 2) 사용자의 실제 구글 달력 스케줄 연동 조회 (MCP Tool)
    google_access_token = await get_valid_google_token(current_user, db)
    user_schedules = await get_google_calendar_events(google_access_token)

    # 3) 해당 지원사업에 등록된 RAG 청크 정보 추출
    chunks = db.query(PolicyChunk).filter(PolicyChunk.policy_id == policy_id).all()
    rag_context = "\n".join([c.chunk_text for c in chunks]) if chunks else "상세 제출 서류 및 우대 조건이 누락되었습니다. 일반 공고 정보에 준합니다."

    # 4) AI 프롬프트 콘텍스트 조립
    deadline_str = policy.apply_end.strftime("%Y-%m-%d")
    schedules_text = "\n".join(user_schedules) if user_schedules else "등록된 개인 일정이 없어 매우 한가한 상태입니다."
    required_docs_text = str(policy.required_documents) if policy.required_documents else "공고 참조"

    system_prompt = (
        "당신은 소상공인 사장님들의 지원금 신청 일정을 밀착 코칭해 주는 친절하고 전문적인 AI 비서 '소복이'입니다. "
        "사장님의 개인 일정이 지원사업 준비에 방해되지 않도록 캘린더 빈틈을 노린 세심한 타임라인 가이드를 짜줍니다."
    )
    
    user_prompt = (
        f"=== [지원사업 상세 정보] ===\n"
        f"- 지원사업명: {policy.title}\n"
        f"- 신청 마감일: {deadline_str}\n"
        f"- 필수 구비 서류: {required_docs_text}\n"
        f"- RAG 상세 서류 요건:\n{rag_context}\n\n"
        f"=== [사장님의 구글 캘린더 스케줄 (향후 2주)] ===\n"
        f"{schedules_text}\n\n"
        f"위 두 가지 데이터를 치밀하게 대조 및 분석하여, "
        f"사장님이 바쁜 구글 개인 일정(겹치는 날)을 피해 접수를 마감 기한 전 무사히 마칠 수 있도록 "
        f"D-14(준비 개시), D-7(우대 증빙 발급 및 보완), D-3(최종 검토), D-Day(접수 완료) "
        f"단계별 구체적인 행동 가이드를 친근하고 상냥한 구어체 톤으로 예쁜 Markdown 형식으로 조율해 작성해 주세요."
    )

    # 5-A) Ollama 로컬 무료 모드 실행 분기
    if COACH_LLM_PROVIDER == "ollama":
        try:
            async with httpx.AsyncClient() as client:
                ollama_payload = {
                    "model": settings.REVIEW_LLM_MODEL,  # exaone3.5
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=ollama_payload,
                    timeout=180.0
                )
                if response.status_code == 200:
                    ai_coach_timeline = response.json().get("message", {}).get("content", "")
                    if ai_coach_timeline:
                        return {
                            "policy_title": policy.title,
                            "deadline": deadline_str,
                            "provider": "ollama",
                            "coach_guide": ai_coach_timeline,
                            "utilized_user_events": len(user_schedules)
                        }
        except Exception:
            pass  # 올라마 서버 에러 시 static fallback으로 우회

    # 5-B) Gemini 모드 실행 분기
    elif COACH_LLM_PROVIDER == "gemini":
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=settings.CHAT_COMPLETION_MODEL or settings.GEMINI_TEXT_MODEL,
                    contents=f"{system_prompt}\n\n{user_prompt}",
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                    ),
                )

                ai_coach_timeline = response.text or ""
                if ai_coach_timeline:
                    return {
                        "policy_title": policy.title,
                        "deadline": deadline_str,
                        "provider": "gemini",
                        "coach_guide": ai_coach_timeline,
                        "utilized_user_events": len(user_schedules)
                    }
            except Exception:
                pass  # Gemini 에러 시 static fallback으로 우회

    # 5-C) OpenAI 상용 유료 모드 실행 분기
    elif COACH_LLM_PROVIDER == "openai":
        openai_api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        if openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_api_key)
                openai_model = settings.CHAT_COMPLETION_MODEL
                if openai_model.startswith("gemini"):
                    openai_model = "gpt-4o-mini"

                response = client.chat.completions.create(
                    model=openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                )
                
                ai_coach_timeline = response.choices[0].message.content or ""
                return {
                    "policy_title": policy.title,
                    "deadline": deadline_str,
                    "provider": "openai",
                    "coach_guide": ai_coach_timeline,
                    "utilized_user_events": len(user_schedules)
                }
            except Exception:
                pass  # OpenAI 에러 시 static fallback으로 우회

    # 5-D) 이중 안전망: LLM 통신 장애 및 설정 오류 시 작동하는 정적 Fallback 알고리즘
    fallback_guide = (
        f"### 🤖 소복이 AI 일정 코칭 타임라인 (Fallback 모드)\n\n"
        f"사장님, **[{policy.title}]** 지원사업 마감일인 **{deadline_str}**에 늦지 않도록 준비 스케줄을 짜드릴게요!\n\n"
        f"📋 **필수 구비 서류**:\n`{required_docs_text}`\n\n"
        f"📅 **사장님의 실제 구글 일정 연동 분석**:\n"
    )
    
    if user_schedules:
        fallback_guide += f"- 향후 2주간 {len(user_schedules)}개의 일정이 감지되었습니다. 마감일 직전에 잡혀있는 사장님의 개인 일정들(예: `{user_schedules[0]}`)과 충돌하지 않도록 조율을 도와드릴게요.\n\n"
    else:
        fallback_guide += "- 향후 2주간 특별한 구글 개인 일정이 확인되지 않았습니다. 한층 넉넉하고 여유롭게 서류를 준비하실 수 있습니다!\n\n"

    fallback_guide += (
        f"🎯 **추천 마감 준비 타임라인**:\n"
        f"1. **D-14 (서류 준비 개시)**: 주민등록등본, 부가가치세과세표준증명원 등 온라인(정부24) 또는 세무서 방문 발급을 시작하세요.\n"
        f"2. **D-7 (우대서류 및 캘린더 대조)**: 감지된 구글 일정을 피해, 마감 1주일 전인 이번 주중에 필수 서류 누락 여부를 확인해 세팅해 둡니다.\n"
        f"3. **D-3 (모의 최종 검수)**: 시스템 접속 폭주 및 서버 지연을 원천 예방하기 위해 오늘 파일 업로드 사전 테스트를 마쳐두세요.\n"
        f"4. **D-Day (접수 마감 완료)**: 늦어도 마감 당일 오전 중에는 접수 완료 버튼을 클릭해 영수증을 챙기셔야 안전합니다!"
    )

    return {
        "policy_title": policy.title,
        "deadline": deadline_str,
        "provider": "static_fallback",
        "coach_guide": fallback_guide,
        "utilized_user_events": len(user_schedules)
    }
