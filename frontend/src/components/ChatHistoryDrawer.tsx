import { useEffect } from 'react'
import { History, LoaderCircle, MessageSquarePlus, Trash2, X } from 'lucide-react'
import type { ChatHistorySession } from '../types'

interface Props {
  open: boolean
  sessions: ChatHistorySession[]
  currentSessionId: string | null
  loading: boolean
  error: string | null
  selectingSessionId: string | null
  deletingSessionId: string | null
  onClose: () => void
  onNewChat: () => void
  onSelect: (session: ChatHistorySession) => void
  onDelete: (session: ChatHistorySession) => void
}

export default function ChatHistoryDrawer({
  open,
  sessions,
  currentSessionId,
  loading,
  error,
  selectingSessionId,
  deletingSessionId,
  onClose,
  onNewChat,
  onSelect,
  onDelete,
}: Props) {
  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose, open])

  const groups = groupSessionsByDate(sessions)

  return (
    <div
      className={`absolute inset-0 z-50 transition-opacity duration-200 motion-reduce:transition-none ${
        open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
      }`}
      aria-hidden={!open}
      inert={!open}
    >
      <button
        type="button"
        aria-label="대화 기록 닫기"
        onClick={onClose}
        className="absolute inset-0 bg-ink/35 backdrop-blur-[1px]"
        tabIndex={open ? 0 : -1}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="내 대화 기록"
        className={`absolute inset-y-0 left-0 flex w-[87%] max-w-[360px] flex-col border-r border-line bg-cream shadow-lift transition-transform duration-300 ease-out motion-reduce:transition-none ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <header className="border-b border-line bg-surface px-5 pb-4 pt-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold tracking-[0.12em] text-primary">나의 정책 상담 장부</p>
              <h2 className="mt-1 text-xl font-extrabold tracking-tight text-ink">대화 기록</h2>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                이전 질문을 다시 열어 이어서 물어볼 수 있어요.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="대화 기록 닫기"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-muted outline-none transition-colors active:bg-line/50 focus-visible:ring-2 focus-visible:ring-primary/25"
            >
              <X size={20} />
            </button>
          </div>

          <button
            type="button"
            onClick={onNewChat}
            className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-white outline-none transition-colors active:bg-primary-hover focus-visible:ring-2 focus-visible:ring-primary/25"
          >
            <MessageSquarePlus size={18} />
            새 대화 시작
          </button>
        </header>

        <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-3 py-4">
          {loading && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-muted">
              <LoaderCircle size={22} className="animate-spin text-primary" />
              <p className="text-sm">대화 기록을 불러오는 중이에요.</p>
            </div>
          )}

          {!loading && error && (
            <div className="rounded-2xl border border-status-red/20 bg-surface p-4">
              <p className="text-sm font-semibold text-status-red">대화 기록을 불러오지 못했어요.</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">{error}</p>
            </div>
          )}

          {!loading && !error && sessions.length === 0 && (
            <div className="flex min-h-56 flex-col items-center justify-center px-6 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-brand">
                <History size={25} />
              </span>
              <p className="mt-4 text-sm font-bold text-ink">아직 저장된 대화가 없어요.</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                질문을 보내면 이곳에 자동으로 차곡차곡 모입니다.
              </p>
            </div>
          )}

          {!loading && !error && groups.map(([label, items]) => (
            <section key={label} className="mb-5 last:mb-0">
              <h3 className="mb-2 px-2 text-[11px] font-bold text-subtle">{label}</h3>
              <div className="space-y-1.5">
                {items.map((session) => {
                  const active = currentSessionId === session.session_id
                  const selecting = selectingSessionId === session.session_id
                  const deleting = deletingSessionId === session.session_id
                  return (
                    <div
                      key={session.session_id}
                      className={`group flex items-stretch rounded-2xl border transition-colors ${
                        active
                          ? 'border-primary/25 bg-primary-soft'
                          : 'border-transparent bg-surface active:border-line'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelect(session)}
                        disabled={selectingSessionId !== null || deletingSessionId !== null}
                        className="min-w-0 flex-1 px-3.5 py-3 text-left outline-none focus-visible:rounded-2xl focus-visible:ring-2 focus-visible:ring-primary/25 disabled:opacity-60"
                      >
                        <span className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate text-[13px] font-bold text-ink">
                            {session.title}
                          </span>
                          {selecting && <LoaderCircle size={14} className="shrink-0 animate-spin text-primary" />}
                        </span>
                        <span className="mt-1 block truncate text-xs text-muted">
                          {session.preview || '대화를 다시 열어보세요.'}
                        </span>
                        <span className="mt-1.5 block text-[10px] font-medium text-subtle">
                          {formatHistoryTime(session.updated_at)} · 메시지 {session.message_count}개
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(session)}
                        disabled={selectingSessionId !== null || deletingSessionId !== null}
                        aria-label={`‘${session.title}’ 대화 삭제`}
                        className="flex w-12 shrink-0 items-center justify-center rounded-r-2xl text-faint outline-none transition-colors active:bg-status-red/10 active:text-status-red focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-status-red/30 disabled:opacity-50"
                      >
                        {deleting ? <LoaderCircle size={16} className="animate-spin" /> : <Trash2 size={16} />}
                      </button>
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      </aside>
    </div>
  )
}

function groupSessionsByDate(sessions: ChatHistorySession[]) {
  const groups = new Map<string, ChatHistorySession[]>()
  sessions.forEach((session) => {
    const label = historyDateLabel(session.updated_at)
    const group = groups.get(label) || []
    group.push(session)
    groups.set(label, group)
  })
  return Array.from(groups.entries())
}

function historyDateLabel(value: string) {
  const date = new Date(value)
  const today = startOfDay(new Date())
  const target = startOfDay(date)
  const dayDifference = Math.round((today.getTime() - target.getTime()) / 86_400_000)
  if (dayDifference === 0) return '오늘'
  if (dayDifference === 1) return '어제'
  if (date.getFullYear() === today.getFullYear()) {
    return `${date.getMonth() + 1}월 ${date.getDate()}일`
  }
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function formatHistoryTime(value: string) {
  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}
