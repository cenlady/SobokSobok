import { useMemo, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Info,
  Plus,
  Sprout,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { benefits } from '../data/benefits'
import { statusMeta, TODAY } from '../lib/format'
import type { BenefitStatus } from '../types'

const WEEK = ['일', '월', '화', '수', '목', '금', '토']

function ymd(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const statusIcon: Record<BenefitStatus, typeof Clock> = {
  closing: Clock,
  open: Sprout,
  notice: Info,
}

export default function CalendarScreen() {
  const navigate = useNavigate()
  // 목업 기준 2024년 6월
  const [cursor, setCursor] = useState({ year: 2024, month: 5 }) // month: 0-indexed
  const [selected, setSelected] = useState(TODAY)

  // 날짜별 혜택 상태 dot 매핑
  const dots = useMemo(() => {
    const map: Record<string, BenefitStatus[]> = {}
    for (const b of benefits) {
      ;(map[b.dueDate] ??= []).push(b.status)
    }
    return map
  }, [])

  const { year, month } = cursor
  const first = new Date(year, month, 1)
  const startDow = first.getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const prevDays = new Date(year, month, 0).getDate()

  // 6주(42칸) 그리드 구성
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
    const ny = year + Math.floor(m / 12)
    const nm = ((m % 12) + 12) % 12
    setCursor({ year: ny, month: nm })
  }

  const dayList = benefits.filter((b) => b.dueDate === selected)
  const selDate = new Date(selected + 'T00:00:00')

  return (
    <div className="pb-24">
      <TopBar />

      {/* 월 캘린더 카드 */}
      <section className="px-5">
        <div className="rounded-3xl bg-white p-5 shadow-card">
          <div className="mb-4 flex items-center justify-between">
            <button className="flex items-center gap-1 text-lg font-bold text-brand-dark">
              {year}년 {month + 1}월
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => shift(-1)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-black/5 text-brand-dark/60 active:bg-black/5"
              >
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={() => shift(1)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-black/5 text-brand-dark/60 active:bg-black/5"
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
                  i === 0 ? 'text-status-red/70' : i === 6 ? 'text-status-blue/70' : 'text-brand-dark/40'
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
                  key={idx}
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
                        key={i}
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

      {/* 선택일 혜택 일정 */}
      <section className="mt-6 px-5">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-brand-dark">
            {selDate.getMonth() + 1}월 {selDate.getDate()}일의 혜택 일정
          </h3>
          <button className="rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-brand">
            전체보기
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {dayList.length === 0 && (
            <p className="rounded-2xl bg-white p-6 text-center text-sm text-brand-dark/40 shadow-card">
              이 날에는 등록된 혜택 일정이 없어요.
            </p>
          )}
          {dayList.map((b) => {
            const meta = statusMeta[b.status]
            const Icon = statusIcon[b.status]
            return (
              <button
                key={b.id}
                onClick={() => navigate(`/benefit/${b.id}`)}
                className="flex w-full items-stretch gap-3 overflow-hidden rounded-2xl bg-white text-left shadow-card active:scale-[0.99]"
              >
                <span className={`w-1.5 flex-shrink-0 ${meta.bar}`} />
                <span
                  className={`my-4 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${meta.iconBg}`}
                >
                  <Icon size={22} className={meta.iconColor} />
                </span>
                <span className="flex-1 py-4 pr-4">
                  <span className="flex items-center justify-between">
                    <span className={`text-sm font-bold ${meta.text}`}>{meta.label}</span>
                    <span className="text-xs font-medium text-brand-dark/50">
                      {b.timeLabel}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-base font-semibold text-brand-dark">
                    {b.title}
                  </span>
                  <span className="mt-0.5 block text-sm text-brand-dark/50">
                    {b.summary}
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        {/* AI 사장님 비서 배너 */}
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-gradient-to-br from-accent-soft to-[#FBD9A8] p-4">
          <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-white/70">
            🤖
          </span>
          <p className="flex-1 text-sm font-medium text-brand-dark">
            <span className="font-bold">AI 사장님 비서</span>
            <br />
            “{month + 1}월에는 사장님이 놓칠 수 있는 마감 혜택이 3건 더 있어요. 확인해볼까요?”
          </p>
          <ChevronRight size={20} className="text-brand-dark/50" />
        </div>
      </section>

      {/* FAB */}
      <button className="fixed bottom-24 left-1/2 z-20 flex h-14 w-14 -translate-x-1/2 items-center justify-center rounded-full bg-brand-dark text-white shadow-xl shadow-brand-dark/30 active:scale-95 sm:left-auto sm:right-[calc(50%-215px+20px)] sm:translate-x-0">
        <Plus size={26} />
      </button>
    </div>
  )
}
