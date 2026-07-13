import { useMemo, useState } from 'react'
import {
  ArrowRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Info,
  Sparkles,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { buildGoogleCalendarUrl, formatDate, toDateKey } from '../lib/calendar'
import { ddayLabel, statusMeta, TODAY } from '../lib/format'
import { useSavedPolicies } from '../lib/storage'
import type { BenefitStatus, SavedPolicy } from '../types'

// 홈은 달력이다. 저장한 정책의 마감일을 한눈에 보여주는 게 앱의 첫 화면.
// 저장한 정책이 없으면 달력이 텅 비므로, 그때만 정책 찾기로 유도한다.

const WEEK = ['일', '월', '화', '수', '목', '금', '토']

function ymd(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function statusForPolicy(policy: SavedPolicy): BenefitStatus {
  const end = toDateKey(policy.apply_end)
  if (!end) return 'notice'
  const today = new Date(`${TODAY}T00:00:00`)
  const due = new Date(`${end}T00:00:00`)
  const diff = Math.round((due.getTime() - today.getTime()) / 86400000)
  return diff <= 14 ? 'closing' : 'open'
}

const statusIcon: Record<BenefitStatus, typeof Clock> = {
  closing: Clock,
  open: CalendarDays,
  notice: Info,
}

export default function HomeScreen() {
  const navigate = useNavigate()
  const { policies, loading } = useSavedPolicies()

  const todayDate = new Date(`${TODAY}T00:00:00`)
  const [cursor, setCursor] = useState({
    year: todayDate.getFullYear(),
    month: todayDate.getMonth(),
  })
  const [selected, setSelected] = useState(TODAY)

  const scheduled = policies.filter((p) => toDateKey(p.apply_end))
  const unscheduled = policies.filter((p) => !toDateKey(p.apply_end))

  const dots = useMemo(() => {
    const map: Record<string, BenefitStatus[]> = {}
    for (const policy of scheduled) {
      const key = toDateKey(policy.apply_end)
      if (!key) continue
      ;(map[key] ??= []).push(statusForPolicy(policy))
    }
    return map
  }, [scheduled])

  const { year, month } = cursor
  const startDow = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const prevDays = new Date(year, month, 0).getDate()

  const cells: { day: number; inMonth: boolean; dateKey?: string }[] = []
  for (let i = 0; i < startDow; i++) {
    cells.push({ day: prevDays - startDow + 1 + i, inMonth: false })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, inMonth: true, dateKey: ymd(year, month, d) })
  }
  let tail = 1
  while (cells.length % 7 !== 0 || cells.length < 42) {
    cells.push({ day: tail++, inMonth: false })
    if (cells.length >= 42) break
  }

  const shift = (dir: number) => {
    const m = month + dir
    setCursor({ year: year + Math.floor(m / 12), month: ((m % 12) + 12) % 12 })
  }

  const dayList = scheduled.filter((p) => toDateKey(p.apply_end) === selected)
  const selDate = new Date(`${selected}T00:00:00`)
  const isEmpty = !loading && policies.length === 0

  return (
    <div className="pb-6">
      <TopBar />

      {/* 달력 */}
      <section className="px-5">
        <div className="rounded-3xl bg-white p-5 shadow-card">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-lg font-bold text-brand-dark">
                {year}년 {month + 1}월
              </p>
              <p className="mt-1 text-xs font-medium text-brand-dark/45">
                저장한 정책의 마감일이 표시돼요.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => shift(-1)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-black/5 text-brand-dark/60 active:bg-black/5"
                aria-label="이전 달"
              >
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={() => shift(1)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-black/5 text-brand-dark/60 active:bg-black/5"
                aria-label="다음 달"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 text-center">
            {WEEK.map((w, i) => (
              <div
                key={w}
                className={`pb-2 text-xs font-semibold ${
                  i === 0
                    ? 'text-status-red/70'
                    : i === 6
                      ? 'text-status-blue/70'
                      : 'text-brand-dark/40'
                }`}
              >
                {w}
              </div>
            ))}
            {cells.map((c, idx) => {
              const isSel = c.dateKey === selected
              const isToday = c.dateKey === TODAY
              const dow = idx % 7
              const dayDots = c.dateKey ? dots[c.dateKey] : undefined
              return (
                <button
                  key={`${c.dateKey ?? 'empty'}-${idx}`}
                  disabled={!c.inMonth}
                  onClick={() => c.dateKey && setSelected(c.dateKey)}
                  className="relative flex flex-col items-center py-1.5"
                >
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-full text-sm ${
                      isSel
                        ? 'bg-brand-dark font-bold text-white'
                        : !c.inMonth
                          ? 'text-brand-dark/20'
                          : isToday
                            ? 'font-bold text-brand'
                            : dow === 0
                              ? 'text-status-red'
                              : dow === 6
                                ? 'text-status-blue'
                                : 'text-brand-dark/80'
                    }`}
                  >
                    {c.day}
                  </span>
                  <span className="mt-1 flex h-1.5 gap-0.5">
                    {dayDots?.slice(0, 3).map((s, i) => (
                      <span
                        key={`${s}-${i}`}
                        className={`h-1.5 w-1.5 rounded-full ${statusMeta[s].bar}`}
                      />
                    ))}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* 저장한 정책이 없으면 여기서 유도한다. 있으면 이 카드는 사라지고 달력이 주인공이 된다. */}
      {isEmpty && (
        <section className="mt-6 px-5">
          <div className="rounded-3xl bg-gradient-to-br from-accent-soft to-[#FBD9A8] p-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/70">
              <Sparkles size={22} className="text-accent" />
            </div>
            <h3 className="mt-4 text-lg font-bold leading-snug text-brand-dark">
              아직 저장한 정책이 없어요
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-brand-dark/70">
              AI가 사장님께 맞는 지원금을 찾아드려요.
              <br />
              저장하면 마감일이 이 달력에 표시돼요.
            </p>
            <button
              onClick={() => navigate('/policies')}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-dark/20 active:scale-[0.99]"
            >
              맞춤 정책 찾아보기 <ArrowRight size={18} />
            </button>
          </div>
        </section>
      )}

      {/* 선택한 날짜의 마감 정책 */}
      {!isEmpty && (
        <section className="mt-6 px-5">
          <h3 className="text-xl font-bold text-brand-dark">
            {selDate.getMonth() + 1}월 {selDate.getDate()}일 마감 정책
          </h3>
          <p className="mt-1 text-sm text-brand-dark/50">
            저장한 정책 {policies.length}건 중 이 날짜 일정이에요.
          </p>

          <div className="mt-4 space-y-3">
            {dayList.length === 0 && (
              <div className="rounded-2xl bg-white p-6 text-center shadow-card">
                <p className="text-sm font-medium text-brand-dark/45">
                  이 날 마감되는 저장 정책이 없어요.
                </p>
              </div>
            )}

            {dayList.map((policy) => (
              <DeadlineCard key={policy.policy_id} policy={policy} />
            ))}
          </div>

          {unscheduled.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-bold text-brand-dark">
                기한 미정 정책 ({unscheduled.length}건)
              </h3>
              <div className="mt-3 space-y-3">
                {unscheduled.map((policy) => (
                  <DeadlineCard key={policy.policy_id} policy={policy} />
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function DeadlineCard({ policy }: { policy: SavedPolicy }) {
  const navigate = useNavigate()
  const end = toDateKey(policy.apply_end)
  const status = statusForPolicy(policy)
  const meta = statusMeta[status]
  const Icon = statusIcon[status]

  return (
    <article className="flex w-full items-stretch gap-3 overflow-hidden rounded-2xl bg-white text-left shadow-card">
      <span className={`w-1.5 flex-shrink-0 ${meta.bar}`} />
      <span
        className={`my-4 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${meta.iconBg}`}
      >
        <Icon size={22} className={meta.iconColor} />
      </span>
      <div className="min-w-0 flex-1 py-4 pr-4">
        <div className="flex items-center justify-between gap-2">
          <span className={`text-sm font-bold ${meta.text}`}>
            {end ? ddayLabel(end) : '기한 미정'}
          </span>
          {policy.support_type && (
            <span className="truncate text-xs font-medium text-brand-dark/50">
              {policy.support_type}
            </span>
          )}
        </div>
        <h4 className="mt-1 line-clamp-2 text-base font-semibold text-brand-dark">
          {policy.title}
        </h4>
        <p className="mt-1 text-sm text-brand-dark/50">
          {formatDate(policy.apply_start)} ~ {formatDate(policy.apply_end)}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate(`/policy/${policy.policy_id}`)}
            className="flex items-center justify-center gap-1 rounded-xl bg-brand-dark px-3 py-2 text-xs font-bold text-white"
          >
            상세보기 <ArrowRight size={13} />
          </button>
          <button
            onClick={() =>
              window.open(buildGoogleCalendarUrl(policy), '_blank', 'noopener,noreferrer')
            }
            className="flex items-center justify-center gap-1 rounded-xl bg-accent-soft px-3 py-2 text-xs font-bold text-accent"
          >
            캘린더 추가
          </button>
        </div>
      </div>
    </article>
  )
}
