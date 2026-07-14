import { useMemo, useState } from 'react'
import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, Compass } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import TopBar from '../components/TopBar'
import { Button, EmptyState, IconButton, LoadingLine, StatusBadge } from '../components/ui'
import { toDateKey } from '../lib/calendar'
import { getDeadlineInfo, formatPeriod, type DeadlineKind } from '../lib/deadline'
import { TODAY } from '../lib/format'
import { useSavedPolicies } from '../lib/storage'
import type { SavedPolicy } from '../types'

// 홈은 달력이다. 저장한 정책의 마감일을 한눈에 보여주는 게 앱의 첫 화면.
//
// 다만 정책의 82%는 마감일이 없다. 그중 대부분은 '상시신청'이라 마감일이 없는 게
// 정상이다. 그걸 '기한 미정'이라는 실패처럼 보이는 말로 묶어두면, 좋은 소식(언제든
// 신청 가능)을 나쁜 소식으로 만든다. 그래서 달력 아래에 따로 섹션을 둔다.

const WEEK = ['일', '월', '화', '수', '목', '금', '토']

function ymd(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
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

  // 마감일이 있는 것만 달력에 찍힌다. 나머지는 성격에 따라 아래 섹션으로 나뉜다.
  const { dated, always, unknown } = useMemo(() => {
    const groups: Record<'dated' | 'always' | 'unknown', SavedPolicy[]> = {
      dated: [],
      always: [],
      unknown: [],
    }
    for (const policy of policies) {
      const kind = getDeadlineInfo(policy).kind
      if (kind === 'urgent' || kind === 'dated') groups.dated.push(policy)
      else if (kind === 'always') groups.always.push(policy)
      else groups.unknown.push(policy)
    }
    return groups
  }, [policies])

  const dots = useMemo(() => {
    const map: Record<string, DeadlineKind[]> = {}
    for (const policy of dated) {
      const key = toDateKey(policy.apply_end)
      if (!key) continue
      ;(map[key] ??= []).push(getDeadlineInfo(policy).kind)
    }
    return map
  }, [dated])

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

  const dayList = dated.filter((p) => toDateKey(p.apply_end) === selected)
  const selDate = new Date(`${selected}T00:00:00`)
  const isEmpty = !loading && policies.length === 0

  if (loading) {
    return (
      <div>
        <TopBar />
        <div className="px-5">
          <LoadingLine message="저장한 정책을 불러오는 중이에요" />
        </div>
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div>
        <TopBar />
        <section className="px-5 pt-2">
          <h2 className="text-title text-ink">내 정책 달력</h2>
        </section>
        <EmptyState
          icon={CalendarDays}
          title="아직 저장한 정책이 없어요"
          description="관심 있는 정책을 저장하면 마감일이 이 달력에 표시돼요."
          actionLabel="맞춤 정책 찾아보기"
          onAction={() => navigate('/policies')}
        />
      </div>
    )
  }

  return (
    <div className="pb-6">
      <TopBar />

      <section className="px-5 pt-2">
        <h2 className="text-title text-ink">내 정책 달력</h2>
        <p className="mt-1 text-sm text-muted">저장한 정책 {policies.length}건</p>
      </section>

      {/* 달력 */}
      <section className="mt-4 px-5">
        <div className="rounded-2xl bg-surface p-5 shadow-card">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-section text-ink">
              {year}년 {month + 1}월
            </p>
            {/* 터치 영역 44×44 — 달력 넘김은 자주 쓰는데 화살표가 작아 누르기 어려웠다 */}
            <div className="-mr-2 flex">
              <IconButton icon={ChevronLeft} onClick={() => shift(-1)} label="이전 달" />
              <IconButton icon={ChevronRight} onClick={() => shift(1)} label="다음 달" />
            </div>
          </div>

          <div className="grid grid-cols-7 text-center">
            {WEEK.map((w) => (
              <div key={w} className="pb-2 text-xs font-medium text-subtle">
                {w}
              </div>
            ))}
            {cells.map((c, idx) => {
              const isSel = c.dateKey === selected
              const isToday = c.dateKey === TODAY
              const dayDots = c.dateKey ? dots[c.dateKey] : undefined
              return (
                <button
                  key={`${c.dateKey ?? 'empty'}-${idx}`}
                  disabled={!c.inMonth}
                  onClick={() => c.dateKey && setSelected(c.dateKey)}
                  // 셀 자체를 44px 높이로. 날짜 하나 고르는 게 이 화면의 주된 조작이다.
                  className="relative flex h-11 flex-col items-center justify-center"
                >
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm ${
                      isSel
                        ? 'bg-ink font-bold text-white'
                        : !c.inMonth
                          ? // 지난달/다음달 날짜. 흐리게 두되 읽을 수는 있어야 한다.
                            // faint(2.4:1)는 텍스트에 쓰면 사실상 안 보인다.
                            'text-subtle/70'
                          : isToday
                            ? 'font-bold text-primary'
                            : 'text-ink'
                    }`}
                  >
                    {c.day}
                  </span>
                  <span className="mt-0.5 flex h-1.5 gap-0.5">
                    {dayDots?.slice(0, 3).map((kind, i) => (
                      <span
                        key={i}
                        className={`h-1.5 w-1.5 rounded-full ${
                          kind === 'urgent' ? 'bg-status-red' : 'bg-muted'
                        }`}
                      />
                    ))}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* 선택한 날짜 */}
      <section className="mt-6 px-5">
        <h3 className="text-section text-ink">
          {selDate.getMonth() + 1}월 {selDate.getDate()}일 마감
        </h3>

        <div className="mt-3 space-y-2.5">
          {dayList.length === 0 ? (
            <p className="rounded-2xl bg-surface px-4 py-5 text-center text-sm text-subtle shadow-card">
              이 날 마감되는 정책이 없어요
            </p>
          ) : (
            dayList.map((policy) => <DeadlineCard key={policy.policy_id} policy={policy} />)
          )}
        </div>
      </section>

      {/* 상시 접수 — 마감이 없다는 건 나쁜 소식이 아니라 좋은 소식이다 */}
      {always.length > 0 && (
        <section className="mt-7 px-5">
          <h3 className="text-section text-ink">상시 접수 가능</h3>
          <p className="mt-1 text-sm text-muted">
            마감 걱정 없이 언제든 신청할 수 있어요. {always.length}건
          </p>
          <div className="mt-3 space-y-2.5">
            {always.map((policy) => (
              <DeadlineCard key={policy.policy_id} policy={policy} />
            ))}
          </div>
        </section>
      )}

      {/* 기간을 우리가 모르는 것들. '상시'라고 둘러대지 않는다. */}
      {unknown.length > 0 && (
        <section className="mt-7 px-5">
          <h3 className="text-section text-ink">기간 확인이 필요해요</h3>
          <p className="mt-1 text-sm text-muted">
            접수 기간이 기관마다 달라요. 공고에서 확인해주세요. {unknown.length}건
          </p>
          <div className="mt-3 space-y-2.5">
            {unknown.map((policy) => (
              <DeadlineCard key={policy.policy_id} policy={policy} />
            ))}
          </div>
        </section>
      )}

      <section className="mt-8 px-5">
        <Button variant="secondary" full onClick={() => navigate('/policies')}>
          <Compass size={16} /> 다른 정책 더 찾아보기
        </Button>
      </section>
    </div>
  )
}

function DeadlineCard({ policy }: { policy: SavedPolicy }) {
  const navigate = useNavigate()
  const info = getDeadlineInfo(policy)
  // 날짜가 없으면 기간 줄을 통째로 숨긴다. "미정 ~ 미정"을 만들지 않는다.
  const period = formatPeriod(policy)

  return (
    <article className="rounded-2xl bg-surface p-4 shadow-card">
      <StatusBadge info={info} />

      <h4 className="mt-2 line-clamp-2 text-card text-ink">{policy.title}</h4>

      {period && <p className="mt-1 text-xs text-subtle">{period}</p>}

      <div className="mt-3 flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/policy/${policy.policy_id}`)}
          className="flex-1"
        >
          상세보기 <ArrowRight size={13} />
        </Button>
        {/* 마감일이 없으면 캘린더에 넣을 날짜도 없다. 버튼 자체를 띄우지 않는다. */}
        {info.calendarable && (
          <AddToCalendarButton policyId={policy.policy_id} applyEnd={policy.apply_end} />
        )}
      </div>
    </article>
  )
}
