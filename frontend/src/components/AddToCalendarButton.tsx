import { useState } from 'react'
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
    } catch (e) {
      setState('error')
      setMessage(
        e instanceof Error && /refresh token/i.test(e.message)
          ? '캘린더 권한이 없어요. 로그아웃 후 다시 로그인해주세요.'
          : '캘린더 등록에 실패했어요.',
      )
    }
  }

  const full = variant === 'full'
  const base = full
    ? 'flex w-full items-center justify-center gap-1.5 rounded-lg border py-3 text-sm font-semibold'
    : 'flex items-center justify-center gap-1 rounded-md border px-2.5 py-2 text-xs font-semibold'

  if (state === 'done') {
    return (
      <a
        href={link ?? '#'}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} border-status-green/20 bg-green-50 text-status-green`}
      >
        <CalendarCheck size={full ? 16 : 13} /> 등록됨
      </a>
    )
  }

  return (
    <div className={full ? 'w-full' : ''}>
      <button
        type="button"
        onClick={add}
        disabled={noDeadline || state === 'loading'}
        title={noDeadline ? '마감일이 정해지지 않아 캘린더에 등록할 수 없어요' : undefined}
        className={`${base} ${
          noDeadline
            ? 'cursor-not-allowed border-line bg-black/[0.025] text-brand-dark/30'
            : 'border-line bg-surface text-brand-dark active:bg-black/[0.03]'
        }`}
      >
        {state === 'loading' ? (
          <>
            <Loader2 size={full ? 16 : 13} className="animate-spin" /> 등록 중…
          </>
        ) : (
          <>
            <CalendarPlus size={full ? 16 : 13} /> 캘린더 추가
          </>
        )}
      </button>

      {state === 'error' && message && (
        <p className="mt-1.5 text-[11px] font-medium leading-snug text-status-red">{message}</p>
      )}
    </div>
  )
}
