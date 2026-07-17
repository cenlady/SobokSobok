import { useEffect, useState } from 'react'
import { CalendarOff, CalendarPlus, CalendarX, Loader2 } from 'lucide-react'
import { apiFetch } from '../lib/api'

interface Props {
  policyId: string
  /** 마감일. 없으면 서버가 400을 내므로 버튼을 비활성화한다. */
  applyEnd?: string | null
  /** 정책 상세처럼 넓은 자리에 놓을 때 */
  variant?: 'compact' | 'full'
}

interface CalendarEventResponse {
  message: string
  google_event_id: string
  html_link: string
}

/**
 * 정책 마감일을 사용자의 구글 캘린더에 등록 및 삭제(연동 해제)한다.
 */
export default function AddToCalendarButton({ policyId, applyEnd, variant = 'compact' }: Props) {
  const noDeadline = !applyEnd
  const [state, setState] = useState<'idle' | 'loading' | 'deleting' | 'done' | 'error'>('idle')
  const [checking, setChecking] = useState(!noDeadline)
  const [message, setMessage] = useState<string | null>(null)

  // [이재혁 - 사전 등록 여부 실시간 비동기 검증]
  useEffect(() => {
    if (noDeadline) return

    let ignore = false
    apiFetch<{ date: string; time: string | null; summary: string; policy_id: string | null; html_link?: string }[]>('/api/v1/calendar/events')
      .then((events) => {
        if (ignore) return
        const matched = events.find(ev => ev.policy_id === policyId)
        if (matched) {
          setState('done')
        }
      })
      .catch((err) => {
        console.warn('사전 캘린더 등록 여부 검증 실패:', err)
      })
      .finally(() => {
        if (!ignore) setChecking(false)
      })

    return () => {
      ignore = true
    }
  }, [policyId, noDeadline])

  const add = async () => {
    if (noDeadline || state === 'loading') return
    setState('loading')
    setMessage(null)
    try {
      await apiFetch<CalendarEventResponse>('/api/v1/calendar/event', {
        method: 'POST',
        json: { policy_id: policyId },
      })
      setState('done')
      // [이재혁 - 실시간 동기화용 변경 플래그 주입]
      sessionStorage.setItem('sobok_calendar_dirty', 'true')
    } catch (e) {
      setState('error')
      let errMsg = '캘린더 등록에 실패했어요.'
      if (e instanceof Error) {
        if (/refresh token/i.test(e.message)) {
          errMsg = '캘린더 권한이 없어요. 로그아웃 후 다시 로그인해주세요.'
        } else if (/이미/i.test(e.message)) {
          errMsg = '이미 등록된 공고입니다.'
          alert('이미 구글 캘린더에 등록 완료된 공고입니다!')
        }
      }
      setMessage(errMsg)
    }
  }

  const remove = async () => {
    if (noDeadline || state === 'deleting') return
    setState('deleting')
    setMessage(null)
    try {
      await apiFetch('/api/v1/calendar/event', {
        method: 'DELETE',
        json: { policy_id: policyId },
      })
      setState('idle')
      sessionStorage.setItem('sobok_calendar_dirty', 'true')
    } catch (e) {
      setState('done')
      alert(e instanceof Error ? e.message : '구글 캘린더 일정 삭제에 실패했어요.')
    }
  }

  const full = variant === 'full'
  // 공용 Button과 같은 치수를 쓴다. 나란히 놓이는 버튼끼리 높이가 다르면 그것만으로도
  // 화면이 어수선해진다.
  const base = full
    ? 'inline-flex h-11 w-full items-center justify-center gap-1 rounded-lg px-3.5 text-[13px] font-semibold'
    : 'inline-flex items-center justify-center gap-1 h-11 px-3 rounded-lg text-[13px] font-semibold'
  const iconSize = full ? 16 : 14

  if (checking) {
    return (
      <div className={full ? 'w-full' : 'shrink-0'}>
        <button
          type="button"
          disabled
          className={`${base} border border-line bg-surface/60 text-subtle animate-pulse cursor-wait`}
        >
          <Loader2 size={iconSize} className="animate-spin text-subtle" /> 확인 중…
        </button>
      </div>
    )
  }

  if (state === 'done' || state === 'deleting') {
    return (
      <div className={full ? 'w-full' : 'shrink-0'}>
        <button
          type="button"
          onClick={remove}
          disabled={state === 'deleting'}
          title="구글 캘린더에서 일정을 삭제합니다"
          className={`${base} transition-colors active:scale-[0.99] bg-status-red/10 text-status-red hover:bg-status-red/20 active:bg-status-red/30`}
        >
          {state === 'deleting' ? (
            <>
              <Loader2 size={iconSize} className="animate-spin text-status-red" /> 삭제 중…
            </>
          ) : (
            <>
              <CalendarX size={iconSize} /> 일정 삭제
            </>
          )}
        </button>
      </div>
    )
  }

  return (
    <div className={full ? 'w-full' : 'shrink-0'}>
      <button
        type="button"
        onClick={add}
        disabled={noDeadline || state === 'loading'}
        title={noDeadline ? '마감일이 정해지지 않아 캘린더에 등록할 수 없어요' : undefined}
        className={`${base} transition-colors active:scale-[0.99] ${
          noDeadline
            ? 'cursor-not-allowed bg-line/60 text-subtle'
            : 'bg-status-green/10 text-status-green hover:bg-status-green/20 active:bg-status-green/30'
        }`}
      >
        {noDeadline ? (
          <>
            <CalendarOff size={iconSize} /> 등록 불가
          </>
        ) : state === 'loading' ? (
          <>
            <Loader2 size={iconSize} className="animate-spin" /> 등록 중…
          </>
        ) : (
          <>
            <CalendarPlus size={iconSize} /> 일정 등록
          </>
        )}
      </button>

      {state === 'error' && message && (
        <p className="mt-1.5 text-[11px] font-medium leading-snug text-status-red">{message}</p>
      )}
    </div>
  )
}
