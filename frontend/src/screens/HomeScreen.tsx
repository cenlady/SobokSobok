import { useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import TopBar from '../components/TopBar'
import { formatDate, toDateKey } from '../lib/calendar'
import { ddayLabel, statusMeta, TODAY } from '../lib/format'
import { useSavedPolicies } from '../lib/storage'
import type { BenefitStatus, SavedPolicy } from '../types'

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

export default function HomeScreen() {
  const navigate = useNavigate()
  const { policies, loading } = useSavedPolicies()

  const todayDate = new Date(`${TODAY}T00:00:00`)
  const [cursor, setCursor] = useState({
    year: todayDate.getFullYear(),
    month: todayDate.getMonth(),
  })
  const [selected, setSelected] = useState(TODAY)

  const scheduled = policies.filter((policy) => toDateKey(policy.apply_end))
  const unscheduled = policies.filter((policy) => !toDateKey(policy.apply_end))
  const ordered = useMemo(
    () =>
      [...scheduled].sort((left, right) => {
        const leftEnd = toDateKey(left.apply_end) || '9999-12-31'
        const rightEnd = toDateKey(right.apply_end) || '9999-12-31'
        const leftPast = leftEnd < TODAY
        const rightPast = rightEnd < TODAY
        if (leftPast !== rightPast) return leftPast ? 1 : -1
        return leftEnd.localeCompare(rightEnd)
      }),
    [scheduled],
  )
  const priority = ordered[0]
  const upcoming = priority
    ? ordered.filter((policy) => policy.policy_id !== priority.policy_id).slice(0, 3)
    : []

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
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push({ day, inMonth: true, dateKey: ymd(year, month, day) })
  }
  let tail = 1
  while (cells.length % 7 !== 0 || cells.length < 42) {
    cells.push({ day: tail++, inMonth: false })
    if (cells.length >= 42) break
  }

  const shift = (direction: number) => {
    const nextMonth = month + direction
    setCursor({
      year: year + Math.floor(nextMonth / 12),
      month: ((nextMonth % 12) + 12) % 12,
    })
  }

  const dayList = scheduled.filter((policy) => toDateKey(policy.apply_end) === selected)
  const selectedDate = new Date(`${selected}T00:00:00`)
  const isEmpty = !loading && policies.length === 0

  return (
    <div className="pb-8">
      <TopBar />

      <section className="px-5 pt-6">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold tracking-[0.08em] text-brand">저장한 정책 일정</p>
            <h2 className="mt-1 page-title">마감 달력</h2>
          </div>
          {!loading && policies.length > 0 && (
            <span className="pb-0.5 text-xs text-muted">저장 {policies.length}건</span>
          )}
        </div>

        <div className="mt-5 flex items-center justify-between">
          <p className="text-base font-semibold text-brand-dark">
            {year}년 {month + 1}월
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => shift(-1)}
              className="flex h-8 w-8 items-center justify-center rounded-md text-brand-dark/55 active:bg-black/5"
              aria-label="이전 달"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={() => shift(1)}
              className="flex h-8 w-8 items-center justify-center rounded-md text-brand-dark/55 active:bg-black/5"
              aria-label="다음 달"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <div className="surface-panel mt-3 p-5">
          <div className="grid grid-cols-7 text-center">
            {WEEK.map((weekday, index) => (
              <div
                key={weekday}
                className={`pb-3 text-[11px] font-medium ${
                  index === 0
                    ? 'text-status-red/75'
                    : index === 6
                      ? 'text-status-blue/75'
                      : 'text-muted'
                }`}
              >
                {weekday}
              </div>
            ))}
            {cells.map((cell, index) => {
              const isSelected = cell.dateKey === selected
              const isToday = cell.dateKey === TODAY
              const dayDots = cell.dateKey ? dots[cell.dateKey] : undefined
              return (
                <button
                  key={`${cell.dateKey ?? 'empty'}-${index}`}
                  disabled={!cell.inMonth}
                  onClick={() => cell.dateKey && setSelected(cell.dateKey)}
                  className="relative flex flex-col items-center py-1.5"
                >
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-md text-sm ${
                      isSelected
                        ? 'bg-brand-dark font-semibold text-white'
                        : !cell.inMonth
                          ? 'text-brand-dark/15'
                          : isToday
                            ? 'border border-brand/40 font-semibold text-brand'
                            : 'text-brand-dark/75'
                    }`}
                  >
                    {cell.day}
                  </span>
                  <span className="mt-1 flex h-1 gap-0.5">
                    {dayDots?.slice(0, 3).map((status, dotIndex) => (
                      <span
                        key={`${status}-${dotIndex}`}
                        className={`h-1 w-1 rounded-full ${statusMeta[status].bar}`}
                      />
                    ))}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {!isEmpty && (
        <section className="mt-5 px-5">
          <h3 className="section-title">
            {selectedDate.getMonth() + 1}월 {selectedDate.getDate()}일 마감
          </h3>
          {dayList.length > 0 ? (
            <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
              {dayList.map((policy) => (
                <DeadlineRow key={policy.policy_id} policy={policy} />
              ))}
            </div>
          ) : (
            <p className="mt-3 border-y border-line py-4 text-sm text-muted">
              이 날 마감되는 저장 정책이 없습니다.
            </p>
          )}

          {unscheduled.length > 0 && (
            <div className="mt-7">
              <h3 className="section-title">마감일 미정</h3>
              <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
                {unscheduled.map((policy) => (
                  <DeadlineRow key={policy.policy_id} policy={policy} />
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <section className="mt-8 border-t border-line px-5 pt-7">
        <p className="text-xs font-semibold tracking-[0.08em] text-brand">오늘의 정책 일정</p>
        <div className="mt-1 flex items-end justify-between gap-3">
          <h2 className="page-title">이번 주 꼭 확인할 정책</h2>
          {!loading && policies.length > 0 && (
            <span className="pb-0.5 text-xs text-muted">저장 {policies.length}건</span>
          )}
        </div>

        {loading && (
          <div className="mt-4 border-y border-line py-5 text-sm text-muted">
            저장한 정책을 불러오는 중입니다.
          </div>
        )}

        {!loading && priority && <PriorityPolicy policy={priority} />}

        {isEmpty && (
          <div className="surface-panel mt-4 border-dashed p-5">
            <h3 className="text-base font-semibold text-brand-dark">저장한 정책이 없습니다</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              내 사업장에 맞는 정책을 저장하면 마감 순서대로 이곳에서 관리할 수 있습니다.
            </p>
            <button onClick={() => navigate('/policies')} className="primary-button mt-4">
              정책 찾아보기
            </button>
          </div>
        )}
      </section>

      {upcoming.length > 0 && (
        <section className="mt-8 px-5">
          <div className="flex items-end justify-between">
            <h3 className="section-title">다가오는 마감</h3>
            <button
              onClick={() => navigate('/policies')}
              className="text-xs font-semibold text-brand active:opacity-60"
            >
              전체 정책 보기
            </button>
          </div>
          <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
            {upcoming.map((policy) => (
              <DeadlineRow key={policy.policy_id} policy={policy} />
            ))}
          </div>
        </section>
      )}

    </div>
  )
}

function PriorityPolicy({ policy }: { policy: SavedPolicy }) {
  const navigate = useNavigate()
  const end = toDateKey(policy.apply_end)

  return (
    <article className="surface-panel mt-4 overflow-hidden border-l-4 border-l-status-red">
      <button
        onClick={() => navigate(`/policy/${policy.policy_id}`)}
        className="flex w-full items-start justify-between gap-4 px-4 py-4 text-left active:bg-black/[0.02]"
      >
        <span className="min-w-0">
          <span className="text-xs font-semibold text-muted">
            {policy.support_type || '지원 정책'}
          </span>
          <strong className="mt-1.5 block line-clamp-2 text-base font-semibold leading-snug text-brand-dark">
            {policy.title}
          </strong>
          <span className="mt-2 block text-xs text-muted">
            {formatDate(policy.apply_start)} ~ {formatDate(policy.apply_end)}
          </span>
        </span>
        <span className="flex-shrink-0 text-lg font-bold tabular-nums text-status-red">
          {end ? ddayLabel(end) : '미정'}
        </span>
      </button>
      <div className="flex items-center justify-between border-t border-line px-4 py-2.5">
        <span className="text-xs text-muted">마감 전에 신청 조건을 확인하세요.</span>
        <AddToCalendarButton policyId={policy.policy_id} applyEnd={policy.apply_end} />
      </div>
    </article>
  )
}

function DeadlineRow({ policy }: { policy: SavedPolicy }) {
  const navigate = useNavigate()
  const end = toDateKey(policy.apply_end)
  const status = statusForPolicy(policy)
  const meta = statusMeta[status]

  return (
    <article className="flex items-center gap-3 bg-surface px-4 py-3.5">
      <span className={`h-9 w-1 flex-shrink-0 rounded-full ${meta.bar}`} aria-hidden="true" />
      <button
        onClick={() => navigate(`/policy/${policy.policy_id}`)}
        className="min-w-0 flex-1 text-left active:opacity-60"
      >
        <span className={`text-xs font-bold ${meta.text}`}>
          {end ? ddayLabel(end) : '마감일 미정'}
        </span>
        <strong className="mt-1 block line-clamp-2 text-sm font-semibold leading-snug text-brand-dark">
          {policy.title}
        </strong>
        <span className="mt-1 flex items-center gap-1 text-xs text-muted">
          <CalendarDays size={12} /> {formatDate(policy.apply_end)}
        </span>
      </button>
      <AddToCalendarButton policyId={policy.policy_id} applyEnd={policy.apply_end} />
    </article>
  )
}
