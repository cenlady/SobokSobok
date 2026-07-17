# -*- coding: utf-8 -*-
# 파일 역할: [일정 관리 도메인] 구글 캘린더 API 연동 및 RAG 기반 AI 코칭 일정 관리 라우터

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, UUID4
import asyncio
import httpx
from datetime import date, datetime, timezone, timedelta
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
    구글 캘린더 API에서 최근 30일부터 향후 1년간의 개인 일정을 조회합니다. (MCP Tool 역할 래퍼)
    시간(dateTime) 정보가 있으면 시/분 범위도 함께 파싱해 반환합니다.

    정상적인 0건과 Google API 장애를 구분해야 한다. 장애를 빈 목록으로 바꾸면
    캘린더 코치가 실제 일정이 많은 사용자에게 "일정이 없다"고 잘못 안내할 수 있다.
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
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Google Calendar 일정 조회 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google Calendar에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google Calendar 일정 조회 중 오류가 발생했습니다.",
            ) from exc

    if response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        raise HTTPException(
            status_code=response.status_code,
            detail="Google Calendar 권한이 만료되었거나 부족합니다. Google 로그인을 다시 연결해 주세요.",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar가 일정 조회 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        )

    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar에서 올바르지 않은 응답을 받았습니다.",
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar에서 올바르지 않은 응답을 받았습니다.",
        )

    schedules = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        summary_value = item.get("summary", "이름 없음")
        summary = summary_value if isinstance(summary_value, str) else "이름 없음"
        description_value = item.get("description", "")
        description = description_value if isinstance(description_value, str) else ""

        # 본문 설명글에서 지원사업ID를 파싱
        policy_id_str = None
        if description:
            match = re.search(r"● 지원사업ID:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", description, re.IGNORECASE)
            if match:
                policy_id_str = match.group(1)

        start_date_obj = item.get("start", {})
        end_date_obj = item.get("end", {})
        if not isinstance(start_date_obj, dict) or not isinstance(end_date_obj, dict):
            continue

        start_dt = start_date_obj.get("dateTime")
        start_d = start_date_obj.get("date")

        if isinstance(start_dt, str) and len(start_dt) >= 16:
            date_str = start_dt[:10]
            start_time = start_dt[11:16]
            end_dt = end_date_obj.get("dateTime")
            end_time = end_dt[11:16] if isinstance(end_dt, str) else None
            time_str = f"{start_time} ~ {end_time}" if end_time else start_time
        elif isinstance(start_d, str) and len(start_d) >= 10:
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
    - 현재 로그인한 유저의 구글 캘린더를 실시간 조회하여 최근 30일부터 향후 1년간의 일정 목록을 반환합니다.
    """
    access_token = await get_valid_google_token(current_user, db)
    return await get_google_calendar_events(access_token)


def _resolve_coaching_dates(
    apply_end: date | datetime,
    target_date: Optional[str],
    *,
    today: date,
) -> tuple[date, date]:
    """실제 마감일과 준비 목표일을 분리하고 안전한 범위만 허용한다."""
    actual_deadline = apply_end.date() if isinstance(apply_end, datetime) else apply_end
    if actual_deadline < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 신청 마감일이 지난 정책입니다.",
        )

    if not target_date:
        return actual_deadline, actual_deadline

    try:
        coaching_target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_date는 YYYY-MM-DD 형식이어야 합니다.",
        ) from exc

    if coaching_target < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="준비 목표일은 오늘 이후여야 합니다.",
        )
    if coaching_target > actual_deadline:
        return actual_deadline, actual_deadline
    return actual_deadline, coaching_target

@router.get("/coach", summary="RAG 일정 관리 AI 가이드 코치 스케줄러")
async def get_calendar_coach_timeline(
    policy_id: Optional[UUID4] = None,
    policy_ids: Optional[List[UUID4]] = Query(None),
    target_date: Optional[str] = None,  # 실제 마감일 이전의 선택적 준비 완료 목표일
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [이재혁 - RAG AI 코칭 영역]
    - RAG 지식(단일 또는 다중 공고 필수 서류 및 우대조건)과 사용자의 실제 구글 일정(MCP 연동)을 융합하여,
      바쁜 개인 일정을 피해 접수를 완수하도록 돕는 D-Day별 초개인화 AI 코칭 타임라인을 제공합니다.
    """
    target_ids: list[UUID4] = []
    if policy_ids:
        for pid in policy_ids:
            if pid and pid not in target_ids:
                target_ids.append(pid)
    if policy_id and policy_id not in target_ids:
        target_ids.append(policy_id)

    if not target_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one policy_id or policy_ids must be provided."
        )

    # 1) 지원사업 조회 및 기본 검사
    policies = db.query(NormalizedPolicy).filter(NormalizedPolicy.id.in_(target_ids)).all()
    if not policies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target policy documents not found."
        )

    policies_with_deadline = [p for p in policies if p.apply_end]
    if not policies_with_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the specified policies have a deadline (apply_end) date."
        )

    model_mode = get_user_model_mode(current_user, "calendar_coach")

    kst = timezone(timedelta(hours=9))
    today_kst = datetime.now(kst).date()

    # 가장 늦은 지원사업 마감일을 기준 마감일로 사용
    latest_apply_end = max([p.apply_end for p in policies_with_deadline])
    actual_deadline_date, coaching_target_date = _resolve_coaching_dates(
        latest_apply_end,
        target_date,
        today=today_kst,
    )

    # 2) 사용자의 실제 구글 달력 스케줄 연동 조회 (MCP Tool)
    google_access_token = await get_valid_google_token(current_user, db)
    user_schedules = await get_google_calendar_events(google_access_token)

    filtered_schedules = []
    for item in user_schedules:
        try:
            item_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if today_kst <= item_date <= coaching_target_date:
                filtered_schedules.append(item)
        except Exception:
            pass

    days_until_target = max((coaching_target_date - today_kst).days, 0)
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]

    schedules_by_date: dict[str, list[dict]] = {}
    for item in filtered_schedules:
        schedules_by_date.setdefault(item["date"], []).append(item)

    busy_day_summaries: list[str] = []
    for date_key in sorted(schedules_by_date.keys()):
        events = schedules_by_date[date_key]
        sample = ", ".join(str(event.get("summary") or "일정") for event in events[:2])
        if len(events) > 2:
            sample += f" 외 {len(events) - 2}건"
        busy_day_summaries.append(f"{date_key}: {len(events)}건 ({sample})")
    busy_days_text = "\n".join(busy_day_summaries[:10]) if busy_day_summaries else "기간 내 등록된 개인 일정이 없습니다."

    quiet_weekdays: list[str] = []
    for day_offset in range(days_until_target + 1):
        candidate_date = today_kst + timedelta(days=day_offset)
        candidate_key = candidate_date.strftime("%Y-%m-%d")
        if candidate_date.weekday() < 5 and candidate_key not in schedules_by_date:
            quiet_weekdays.append(f"{candidate_key} ({weekday_names[candidate_date.weekday()]})")
        if len(quiet_weekdays) >= 5:
            break
    quiet_days_text = ", ".join(quiet_weekdays) if quiet_weekdays else "기간 내 비어 있는 평일이 부족합니다. 짧은 확인 작업 중심으로 배치하세요."

    timeline_headings: list[str] = []
    seen_headings: set[str] = set()

    def add_timeline_heading(day_label: str, phase_date: date, title: str) -> None:
        if phase_date < today_kst or phase_date > coaching_target_date or day_label in seen_headings:
            return
        seen_headings.add(day_label)
        date_label = f"{phase_date.year}년 {phase_date.month}월 {phase_date.day}일"
        timeline_headings.append(f"{day_label} ({date_label}) - {title}")

    today_day_label = "D-Day" if days_until_target == 0 else f"D-{days_until_target}"
    add_timeline_heading(today_day_label, today_kst, "오늘 우선순위")
    for offset, title in [
        (14, "준비 개시"),
        (7, "우대 증빙 발급 및 보완"),
        (3, "최종 검토"),
        (0, "접수 완료"),
    ]:
        phase_date = coaching_target_date - timedelta(days=offset)
        day_label = "D-Day" if offset == 0 else f"D-{offset}"
        add_timeline_heading(day_label, phase_date, title)
    timeline_headings_text = "\n".join(timeline_headings)

    # 3) 각 지원사업에 등록된 필수 서류 및 RAG 청크 정보 추출
    all_doc_names: list[str] = []
    policy_details_text_list: list[str] = []

    for idx, p in enumerate(policies_with_deadline, 1):
        p_deadline = p.apply_end.strftime("%Y-%m-%d") if p.apply_end else "미정"
        p_docs: list[str] = []
        if p.required_documents:
            if isinstance(p.required_documents, list):
                for doc in p.required_documents:
                    if isinstance(doc, dict) and "name" in doc:
                        p_docs.append(str(doc["name"]))
                    elif isinstance(doc, str):
                        p_docs.append(doc)
            elif isinstance(p.required_documents, str):
                p_docs.append(p.required_documents)

        all_doc_names.extend(p_docs)
        doc_summary = ", ".join(p_docs) if p_docs else "공고 참조"

        chunks = db.query(PolicyChunk).filter(PolicyChunk.policy_id == p.id).all()
        rag_context = "\n".join([c.chunk_text for c in chunks[:3]]) if chunks else "상세 제출 서류 요건 없음"

        policy_details_text_list.append(
            f"● [지원사업 #{idx}] {p.title}\n"
            f"  - 마감일: {p_deadline}\n"
            f"  - 제출서류: {doc_summary}\n"
            f"  - RAG 상세 요건:\n{rag_context}"
        )

    policies_context_text = "\n\n".join(policy_details_text_list)

    unique_doc_names = list(dict.fromkeys([d.strip() for d in all_doc_names if d and isinstance(d, str)]))
    prep_results = search_prep_guides(
        db,
        ", ".join(unique_doc_names),
        model_mode=model_mode,
        limit=min(max(len(unique_doc_names), 1), 10),
    ) if unique_doc_names else []

    prep_guides_text = "등록된 서류 발급 가이드가 없습니다."
    if prep_results:
        prep_guides_text = "\n\n".join(
            f"[{row.document_name}]\n{row.guide_text}"
            for row, _similarity in prep_results
            if row.guide_text
        )

    # 4) AI 프롬프트 콘텍스트 조립
    deadline_str = actual_deadline_date.strftime("%Y-%m-%d")
    coaching_target_str = coaching_target_date.strftime("%Y-%m-%d")
    schedules_list = []
    for item in filtered_schedules:
        time_part = f" ({item['time']})" if item.get('time') else ""
        schedules_list.append(f"{item['date']}{time_part}: {item['summary']}")
    schedules_text = "\n".join(schedules_list) if schedules_list else "준비 기간 안에 등록된 개인 일정이 없습니다."

    is_multi = len(policies_with_deadline) > 1
    system_prompt = (
        "당신은 소상공인 사장님들의 지원금 신청 일정을 밀착 코칭해 주는 전문 AI 비서 '소복이'입니다. "
        "응답은 모바일 하단 시트의 카드형 체크리스트로 표시됩니다. "
        "사용자가 바로 실행할 수 있도록 짧고 구체적인 행동 중심으로 안내하세요.\n"
        "[작성 원칙]\n"
        "1. 공고, RAG 상세 요건, 서류 발급 가이드에 없는 서류나 자격조건을 지어내지 마세요.\n"
        "2. 복수 정책의 공통 구비 서류(예: 주민등록등본, 사업자등록증 등)는 한가한 날 한 번에 묶어서 발급받도록 안내하세요.\n"
        "3. 사용자의 바쁜 날짜에는 방문, 발급, 제출 같은 집중 작업을 배치하지 말고 빈 평일 후보를 우선 활용하세요.\n"
        "4. 각 행동은 '확인하기', '발급하기', '저장하기', '제출하기'처럼 사용자가 바로 할 수 있는 동사형으로 쓰세요.\n"
        "5. 한 문장은 38자 안팎으로 짧게 쓰고, 같은 말을 반복하지 마세요.\n"
        "[출력 형식]\n"
        "첫 줄은 반드시 '한줄요약: ...' 형식으로 작성하세요.\n"
        "그 다음에는 사용자가 제공받은 단계 제목만 그대로 사용하세요.\n"
        "각 단계마다 번호 항목 2~3개를 쓰고, 각 번호 아래에는 • 불릿 1~2개를 쓰세요.\n"
        "마크다운 제목, 굵게, 코드, 표, JSON, 하이픈 불릿, 이모지는 사용하지 마세요."
    )

    user_prompt = (
        f"=== [지원사업 상세 정보 ({len(policies_with_deadline)}건)] ===\n"
        f"{policies_context_text}\n\n"
        f"- 서류 발급 통합 가이드:\n{prep_guides_text}\n\n"
        f"=== [사장님의 구글 캘린더 스케줄] ===\n"
        f"{schedules_text}\n\n"
        f"=== [일정 분석] ===\n"
        f"- 바쁜 날짜 요약:\n{busy_days_text}\n"
        f"- 발급/방문 추천 후보일: {quiet_days_text}\n\n"
        f"=== [반드시 사용할 단계 제목] ===\n"
        f"{timeline_headings_text}\n\n"
        f"위 데이터를 대조하여, 오늘부터 목표일까지 실제로 끝낼 수 있는 "
        f"{'통합 ' if is_multi else ''}신청 준비 체크리스트를 작성하세요. "
        f"{'여러 정책의 공통 서류 한 번에 묶어서 발급하기, 마감일이 빠른 공고 우선 준비, ' if is_multi else ''}"
        f"캘린더가 바쁜 날 회피를 반드시 반영하세요."
    )

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

    main_title = policies_with_deadline[0].title
    display_title = main_title if len(policies_with_deadline) == 1 else f"{main_title} 외 {len(policies_with_deadline)-1}건"

    return {
        "policy_title": display_title,
        "policy_count": len(policies_with_deadline),
        "deadline": deadline_str,
        "target_date": coaching_target_str,
        "provider": model_spec.provider,
        "prep_embedding_provider": "openai" if model_mode == "cloud" else "ollama",
        "prep_guides_used": len(prep_results),
        "coach_guide": ai_coach_timeline,
        "utilized_user_events": len(filtered_schedules),
        "total_user_events": len(user_schedules),
    }
