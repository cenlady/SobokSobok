import { useEffect, useState } from 'react'
import { CalendarCheck, CalendarPlus, Loader2 } from 'lucide-react'
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
 * 정책 마감일을 사용자의 구글 캘린더에 등록한다.
 *
 * 예전에는 구글 캘린더의 "일정 추가" 화면을 새 탭으로 여는 TEMPLATE URL을 썼다.
 * 그 방식은 사용자가 새 탭에서 '저장'을 한 번 더 눌러야 실제로 등록됐다.
 * 이제 서버가 Calendar API로 직접 등록한다 — 버튼 한 번이면 끝난다.
 * (구글 토큰은 users 테이블에 있고 서버 밖으로 나가지 않는다.)
 */
export default function AddToCalendarButton({ policyId, applyEnd, variant = 'compact' }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [link, setLink] = useState<string | null>(null)

  // 마감일이 없는 정책은 캘린더에 넣을 날짜가 없다. 눌러봐야 서버가 400을 낸다.
  const noDeadline = !applyEnd

  // [이재혁 - 사전 등록 여부 실시간 비동기 검증]
  useEffect(() => {
    if (noDeadline) return

    let ignore = false
    apiFetch<{ date: string; time: string | null; summary: string; policy_id: string | null; html_link?: string }[]>('/api/v1/calendar/events')
      .then((events) => {
        if (ignore) return
        const matched = events.find(ev => ev.policy_id === policyId)
        if (matched) {
          setLink(matched.html_link ?? null)
          setState('done')
        }
      })
      .catch((err) => {
        console.warn('사전 캘린더 등록 여부 검증 실패:', err)
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
      const data = await apiFetch<CalendarEventResponse>('/api/v1/calendar/event', {
        method: 'POST',
        json: { policy_id: policyId },
      })
      setLink(data.html_link)
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

  const full = variant === 'full'
  // 공용 Button과 같은 치수를 쓴다. 나란히 놓이는 버튼끼리 높이가 다르면 그것만으로도
  // 화면이 어수선해진다.
  const base = full
    ? 'inline-flex h-11 w-full items-center justify-center gap-1 rounded-lg px-3.5 text-[13px] font-semibold'
    : 'inline-flex items-center justify-center gap-1 h-11 px-3 rounded-lg text-[13px] font-semibold'
  const iconSize = full ? 16 : 14

  if (state === 'done') {
    return (
      <a
        href={link ?? '#'}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} shrink-0 bg-status-green/10 text-status-green`}
      >
        <CalendarCheck size={iconSize} /> 등록됨
      </a>
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
            : full
              ? 'bg-accent-soft text-brand active:bg-accent-soft/70'
              : 'border border-line bg-surface text-muted active:bg-line/40'
        }`}
      >
        {state === 'loading' ? (
          <>
            <Loader2 size={iconSize} className="animate-spin" /> 등록 중…
          </>
        ) : (
          <>
            <CalendarPlus size={iconSize} /> 캘린더
          </>
        )}
      </button>

      {state === 'error' && message && (
        <p className="mt-1.5 text-[11px] font-medium leading-snug text-status-red">{message}</p>
      )}
    </div>
  )
}
