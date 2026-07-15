# -*- coding: utf-8 -*-
# 파일 역할: [일정 관리 도메인] 구글 캘린더 API 연동 및 RAG 기반 AI 코칭 일정 관리 라우터

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, UUID4
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import re

from app.core.database import get_db
# 인증은 우리 JWT로 한다(app/core/deps). 구글 access token을 브라우저에 넘기지 않으므로
# 요청 헤더로는 구글 토큰이 오지 않는다. 아래 get_valid_google_token()이 users 테이블에서
# 꺼내 쓰고, 만료되면 refresh_token으로 갱신한다 — 구글 토큰은 서버 밖으로 나가지 않는다.
from app.core.deps import get_current_user
from app.models.user import User
from app.models.normalized_policy import NormalizedPolicy
from app.models.chat import PolicyChunk
from app.core.config import settings
from app.core.model_errors import ModelResponseError
from app.core.model_provider import get_chat_model, get_user_model_mode
from app.services.prep_rag import search_prep_guides

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

async def get_google_calendar_events(access_token: str) -> List[dict]:
    """
    구글 캘린더 API를 찔러 사용자의 향후 2주일간의 개인 일정을 조회합니다. (MCP Tool 역할 래퍼)
    시간(dateTime) 정보가 있으면 시/분 범위도 함께 파싱해 반환합니다.
    """
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=30)).isoformat()
    time_max = (now + timedelta(days=365)).isoformat()
    
    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250
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
                description = item.get("description", "")

                # 본문 설명글에서 지원사업ID를 파싱
                policy_id_str = None
                if description:
                    match = re.search(r"● 지원사업ID:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", description, re.IGNORECASE)
                    if match:
                        policy_id_str = match.group(1)

                start_date_obj = item.get("start", {})
                end_date_obj = item.get("end", {})

                start_dt = start_date_obj.get("dateTime")
                start_d = start_date_obj.get("date")

                if start_dt:
                    date_str = start_dt[:10]
                    start_time = start_dt[11:16]
                    end_dt = end_date_obj.get("dateTime")
                    end_time = end_dt[11:16] if end_dt else None
                    time_str = f"{start_time} ~ {end_time}" if end_time else start_time
                elif start_d:
                    date_str = start_d[:10]
                    time_str = None
                else:
                    continue

                schedules.append({
                    "date": date_str,
                    "time": time_str,
                    "summary": summary,
                    "policy_id": policy_id_str
                })
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

    # 중복 체크: 구글 일정에서 동일한 마감 일정이 이미 연동되어 있는지 실시간 검증
    existing_events = await get_google_calendar_events(access_token)
    target_summary = f"[소복소복] {policy.title} 신청 마감"
    for ev in existing_events:
        if ev.get("summary") == target_summary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 구글 캘린더에 연동된 공고입니다."
            )

    start_date_str = policy.apply_end.strftime("%Y-%m-%d")
    end_date = policy.apply_end + timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")

    event_body = {
        "summary": f"[소복소복] {policy.title} 신청 마감",
        "description": (
            f"● 지원사업명: {policy.title}\n"
            f"● 소관기관: {policy.organization or '확인불가'}\n"
            f"● 온라인 신청 주소: {policy.apply_url or '외부 링크가 명시되지 않음'}\n"
            f"● 지원사업ID: {policy.id}\n\n"
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

@router.get("/events", summary="구글 캘린더 개인 일정 목록 조회")
async def get_my_google_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - 캘린더 영역]
    - 현재 로그인한 유저의 구글 캘린더를 실시간 조회하여 향후 2주간의 일정 목록을 반환합니다.
    """
    try:
        access_token = await get_valid_google_token(current_user, db)
        return await get_google_calendar_events(access_token)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        return []

@router.get("/coach", summary="RAG 일정 관리 AI 가이드 코치 스케줄러")
async def get_calendar_coach_timeline(
    policy_id: UUID4,
    target_date: Optional[str] = None,  # [이재혁 - 동적 오버라이드 목표일]
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - RAG AI 코칭 영역]
    - RAG 지식(공고 필수 서류 및 우대조건)과 사용자의 실제 구글 일정(MCP 연동)을 융합하여,
      바쁜 개인 일정을 피해 접수를 완수하도록 돕는 D-Day별 초개인화 AI 코칭 타임라인을 제공합니다.
    """
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

    model_mode = get_user_model_mode(current_user, "calendar_coach")

    # 2) 사용자의 실제 구글 달력 스케줄 연동 조회 (MCP Tool)
    google_access_token = await get_valid_google_token(current_user, db)
    user_schedules = await get_google_calendar_events(google_access_token)

    # AI 코칭용: 오늘부터 해당 지원사업 마감일(policy.apply_end) 또는 사장님이 선택한 목표 날짜(target_date) 당일까지 필터링
    now_utc = datetime.now(timezone.utc)

    if target_date:
        try:
            deadline_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except Exception:
            deadline_date = policy.apply_end.date() if hasattr(policy.apply_end, "date") else policy.apply_end
    else:
        deadline_date = policy.apply_end.date() if hasattr(policy.apply_end, "date") else policy.apply_end

    filtered_schedules = []
    for item in user_schedules:
        try:
            item_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            # 오늘부터 지정된 목표일 당일까지의 스케줄만 수집
            if now_utc.date() <= item_date <= deadline_date:
                filtered_schedules.append(item)
        except Exception:
            filtered_schedules.append(item)

    # 3) 해당 지원사업에 등록된 RAG 청크 정보 추출
    chunks = db.query(PolicyChunk).filter(PolicyChunk.policy_id == policy_id).all()
    rag_context = "\n".join([c.chunk_text for c in chunks]) if chunks else "상세 제출 서류 및 우대 조건이 누락되었습니다. 일반 공고 정보에 준합니다."

    # 4) AI 프롬프트 콘텍스트 조립
    deadline_str = deadline_date.strftime("%Y-%m-%d")
    schedules_list = []
    for item in filtered_schedules:
        time_part = f" ({item['time']})" if item.get('time') else ""
        schedules_list.append(f"{item['date']}{time_part}: {item['summary']}")
    schedules_text = "\n".join(schedules_list) if schedules_list else "등록된 개인 일정이 없어 매우 한가한 상태입니다."
    required_docs_text = "공고 참조"
    doc_names: list[str] = []
    if policy.required_documents:
        if isinstance(policy.required_documents, list):
            for doc in policy.required_documents:
                if isinstance(doc, dict) and "name" in doc:
                    doc_names.append(doc["name"])
                elif isinstance(doc, str):
                    doc_names.append(doc)
            if doc_names:
                required_docs_text = ", ".join(doc_names)
            else:
                required_docs_text = str(policy.required_documents)
        else:
            required_docs_text = str(policy.required_documents)

    prep_results = search_prep_guides(
        db,
        ", ".join(doc_names),
        model_mode=model_mode,
        limit=min(max(len(doc_names), 1), 8),
    )
    prep_guides_text = "등록된 서류 발급 가이드가 없습니다."
    if prep_results:
        prep_guides_text = "\n\n".join(
            f"[{row.document_name}]\n{row.guide_text}"
            for row, _similarity in prep_results
            if row.guide_text
        )

    system_prompt = (
        "당신은 소상공인 사장님들의 지원금 신청 일정을 밀착 코칭해 주는 친절하고 전문적인 AI 비서 '소복이'입니다. "
        "사장님의 개인 일정이 지원사업 준비에 방해되지 않도록 캘린더 빈틈을 노린 세심한 타임라인 가이드를 짜줍니다.\n"
        "[중요형식지침]: 마크다운 특수기호(샵 #, 별표 *, 백틱 ` 등)를 절대 사용하지 마세요. "
        "오직 줄바꿈(엔터), 번호 매기기(1., 2.), 그리고 적절한 이모지만을 활용하여, "
        "모바일 화면에서 바로 읽기 쉬운 깔끔한 플레인 텍스트로만 응답해야 합니다."
    )
    
    user_prompt = (
        f"=== [지원사업 상세 정보] ===\n"
        f"- 지원사업명: {policy.title}\n"
        f"- 신청 마감일: {deadline_str}\n"
        f"- 필수 구비 서류: {required_docs_text}\n"
        f"- RAG 상세 서류 요건:\n{rag_context}\n\n"
        f"- 서류 발급 가이드:\n{prep_guides_text}\n\n"
        f"=== [사장님의 구글 캘린더 스케줄] ===\n"
        f"{schedules_text}\n\n"
        f"위 두 가지 데이터를 치밀하게 대조 및 분석하여, "
        f"사장님이 바쁜 구글 개인 일정(겹치는 날)을 피해 접수를 마감 기한 전 무사히 마칠 수 있도록 "
        f"D-14(준비 개시), D-7(우대 증빙 발급 및 보완), D-3(최종 검토), D-Day(접수 완료) "
        f"단계별 구체적인 행동 가이드를 친근하고 상냥한 구어체 톤으로 작성해 주세요.\n"
        f"[필수]: 절대로 # 이나 * 같은 마크다운 특수 기호를 내용에 포함하지 말고, 순수 한글 텍스트와 이모지로만 읽기 쉽게 줄바꿈해 출력하세요."
    )

    # 5) 캘린더 CRUD와 분리된 AI 코치 전용 모델 설정을 사용한다.
    model = get_chat_model("calendar_coach", model_mode=model_mode)
    model_spec = model.spec
    ai_coach_timeline = await asyncio.to_thread(
        model.generate,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        stage="calendar_timeline_generation",
        source_module=__name__,
        source_function="get_calendar_coach_timeline",
        temperature=0.3,
        timeout_seconds=settings.LLM_REQUEST_TIMEOUT_SECONDS,
    )
    if not ai_coach_timeline:
        raise ModelResponseError("캘린더 코치 모델이 빈 응답을 반환했습니다.")
    return {
        "policy_title": policy.title,
        "deadline": deadline_str,
        "provider": model_spec.provider,
        "prep_embedding_provider": "openai" if model_mode == "cloud" else "ollama",
        "prep_guides_used": len(prep_results),
        "coach_guide": ai_coach_timeline,
        "utilized_user_events": len(user_schedules),
    }
