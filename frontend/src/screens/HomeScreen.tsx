import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Compass, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import TopBar from '../components/TopBar'
import {
  Button,
  EmptyState,
  IconButton,
  PageIntro,
  StatusBadge,
  TagList,
} from '../components/ui'
import { localDateKey, toDateKey } from '../lib/calendar'
import { getDeadlineInfo, formatPeriod, type DeadlineKind } from '../lib/deadline'
import { TODAY } from '../lib/format'
import { getPolicyLabels } from '../lib/policyLabels'
import { useProfile, useSavedPolicies } from '../lib/storage'
import { apiFetch } from '../lib/api'
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
  const { loading: profileLoading } = useProfile()

  const todayDate = new Date(`${TODAY}T00:00:00`)
  const [cursor, setCursor] = useState({
    year: todayDate.getFullYear(),
    month: todayDate.getMonth(),
  })
  const [selected, setSelected] = useState(TODAY)

  // [이재혁 - 실시간 구글 캘린더 개인 일정 연동 상태]
  const [googleEvents, setGoogleEvents] = useState<{ date: string; time: string | null; summary: string; policy_id: string | null }[]>([])
  const [googleEventsLoading, setGoogleEventsLoading] = useState(true)
  const [googleEventsError, setGoogleEventsError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    // 기본 패치 헬퍼
    const fetchEvents = () => {
      setGoogleEventsLoading(true)
      setGoogleEventsError(null)
      apiFetch<{ date: string; time: string | null; summary: string; policy_id: string | null }[]>('/api/v1/calendar/events')
        .then((data) => {
          if (!ignore) {
            setGoogleEvents(data)
            setGoogleEventsError(null)
            sessionStorage.removeItem('sobok_calendar_dirty')
          }
        })
        .catch((err) => {
          if (!ignore) {
            setGoogleEventsError(err instanceof Error ? err.message : 'Google Calendar 일정을 불러오지 못했습니다.')
          }
          console.warn('Google Calendar 일정을 조회할 수 없습니다:', err)
        })
        .finally(() => {
          if (!ignore) setGoogleEventsLoading(false)
        })
    }

    // [이재혁 - 실시간 동기화 플래그 감지용 헬퍼]
    const checkDirtyAndFetch = () => {
      const isDirty = sessionStorage.getItem('sobok_calendar_dirty') === 'true'
      if (isDirty) {
        fetchEvents()
      }
    }

    // 최초 화면 마운트 시 조회
    fetchEvents()

    // 화면 복원(pageshow), 탭 포커스(focus) 감지 리스너 바인딩
    window.addEventListener('pageshow', checkDirtyAndFetch)
    window.addEventListener('focus', checkDirtyAndFetch)

    return () => {
      ignore = true
      window.removeEventListener('pageshow', checkDirtyAndFetch)
      window.removeEventListener('focus', checkDirtyAndFetch)
    }
  }, [])

  const googleEventsMap = useMemo(() => {
    const map: Record<string, { time: string | null; summary: string; policy_id: string | null }[]> = {}
    for (const ev of googleEvents) {
      ;(map[ev.date] ??= []).push({ time: ev.time, summary: ev.summary, policy_id: ev.policy_id })
    }
    return map
  }, [googleEvents])

  // 저장한 일정과 공고를 함께 확인하는 일정 안내 상태
  const [coachGuide, setCoachGuide] = useState<string | null>(null)
  const [loadingCoach, setLoadingCoach] = useState(false)
  const [isOpenCoachModal, setIsOpenCoachModal] = useState(false)
  const modalCloseButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isOpenCoachModal) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpenCoachModal(false)
    }
    const previousOverflow = document.body.style.overflow
    const frame = window.requestAnimationFrame(() => modalCloseButtonRef.current?.focus())

    document.addEventListener('keydown', onKeyDown)
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      window.cancelAnimationFrame(frame)
    }
  }, [isOpenCoachModal])

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
  const todayKey = localDateKey(new Date())
  const isPastDate = selected < todayKey
  const policySchedulesInRange = googleEvents
    .filter((event) => Boolean(event.policy_id) && todayKey <= event.date && event.date <= selected)
    .sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? '').localeCompare(b.time ?? ''))
  const hasPolicyScheduleInRange = policySchedulesInRange.length > 0

  // 오늘부터 선택일까지의 정책 일정을 기준으로 신청 준비 순서를 불러온다.
  const handleCoachTimeline = async () => {
    if (googleEventsError) {
      alert('Google Calendar 일정을 불러오지 못해 신청 일정을 안내할 수 없습니다. Google 로그인을 다시 연결하거나 잠시 후 다시 시도해 주세요.')
      return
    }

    // 기간의 첫 정책을 대표 공고로 사용하되, 서버에는 목표일을 함께 보내
    // 오늘부터 선택일까지 포함된 모든 캘린더 일정을 고려하게 한다.
    const targetPolicyId = policySchedulesInRange[0]?.policy_id
    if (!targetPolicyId) return
    if (loadingCoach) return
    setCoachGuide(null)
    setIsOpenCoachModal(true)
    setLoadingCoach(true)
    try {
      const data = await apiFetch<{ coach_guide: string }>(
        `/api/v1/calendar/coach?policy_id=${encodeURIComponent(targetPolicyId)}&target_date=${selected}`,
      )
      setCoachGuide(data.coach_guide)
    } catch (e) {
      alert(e instanceof Error ? e.message : '일정 안내를 불러오지 못했어요. 캘린더 연동 상태를 확인해 주세요.')
      setIsOpenCoachModal(false)
    } finally {
      setLoadingCoach(false)
    }
  }
  const selDate = new Date(`${selected}T00:00:00`)
  const homeLoading = loading || profileLoading || googleEventsLoading
  const isEmpty = !homeLoading && !googleEventsError && policies.length === 0 && googleEvents.length === 0

  if (homeLoading) return <HomeScreenSkeleton />

  if (isEmpty) {
    return (
      <div>
        <TopBar />
        <PageIntro title="내 정책 달력" />
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
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <TopBar />

      <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain pb-6">
        <PageIntro title="내 정책 달력" description={`저장한 정책 ${policies.length}건`} />

      {googleEventsError && (
        <section className="mt-4 px-5">
          <div className="rounded-2xl border border-status-red/20 bg-status-red/5 px-4 py-3.5">
            <p className="text-sm font-bold text-status-red">Google Calendar 일정을 불러오지 못했어요</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              일정 0건으로 처리하지 않았습니다. Google 로그인을 다시 연결하거나 잠시 후 화면을 다시 열어주세요.
            </p>
          </div>
        </section>
      )}

      {/* 달력 */}
      <section className="mt-4 px-5">
        <div className="surface-panel p-5">
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
              const hasGoogle = c.dateKey ? Boolean(googleEventsMap[c.dateKey]) : false
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
                    {dayDots?.slice(0, 2).map((kind, i) => (
                      <span
                        key={i}
                        className={`h-1.5 w-1.5 rounded-full ${
                          kind === 'urgent' ? 'bg-status-red' : 'bg-muted'
                        }`}
                      />
                    ))}
                    {hasGoogle && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
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
          {selDate.getMonth() + 1}월 {selDate.getDate()}일 일정
        </h3>

        <div className="mt-3 space-y-2.5">
          {(() => {
            const selGoogleEvents = googleEventsMap[selected] || []
            const hasNoEvents = dayList.length === 0 && selGoogleEvents.length === 0

            return (
              <>
                {selGoogleEvents.length > 0 && (
                  <div className="surface-panel divide-y divide-line overflow-hidden">
                    {selGoogleEvents.map((ev, i) => (
                      <div key={`${ev.summary}-${i}`} className="flex items-center gap-3 px-4 py-3.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-brand">
                          <CalendarDays size={16} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-semibold text-subtle">캘린더 일정</span>
                            {ev.time && (
                              <span className="rounded-md bg-line px-2 py-0.5 text-[11px] font-semibold text-muted">
                                {ev.time}
                              </span>
                            )}
                          </div>
                          <p className="mt-1 truncate text-sm font-semibold leading-snug text-ink">{ev.summary}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {hasNoEvents ? (
                  <p className="surface-panel px-4 py-5 text-center text-sm text-subtle">
                    이 날 등록된 일정이 없어요
                  </p>
                ) : null}
                {dayList.length > 0 && (
                  <div className="surface-panel divide-y divide-line overflow-hidden">
                    {dayList.map((policy) => (
                      <DeadlineCard key={policy.policy_id} policy={policy} />
                    ))}
                  </div>
                )}
              </>
            )
          })()}
        </div>
      </section>

      {/* 상시 접수 — 마감이 없다는 건 나쁜 소식이 아니라 좋은 소식이다 */}
      {always.length > 0 && (
        <section className="mt-7 px-5">
          <h3 className="text-section text-ink">상시 접수 가능</h3>
          <p className="mt-1 text-sm text-muted">
            마감 걱정 없이 언제든 신청할 수 있어요. {always.length}건
          </p>
          <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
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
          <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
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

      <div className="shrink-0 border-t border-line bg-cream/95 px-5 py-3 backdrop-blur">
        <Button onClick={handleCoachTimeline} disabled={loadingCoach || isPastDate || !hasPolicyScheduleInRange} full>
          {loadingCoach ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted border-t-transparent" />
          ) : (
            <CalendarDays size={16} />
          )}
          {isPastDate
            ? '오늘 이후 날짜만 안내받을 수 있어요'
            : !hasPolicyScheduleInRange
              ? '해당 기간 내에 정책 일정이 없습니다'
              : '신청 일정 안내 받기'}
        </Button>
      </div>

      {/* 신청 일정 안내 */}
      {isOpenCoachModal && (coachGuide || loadingCoach) && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-4"
          onClick={() => setIsOpenCoachModal(false)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="coach-modal-title"
            className="relative flex max-h-[86dvh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl border border-line bg-cream shadow-2xl sm:max-h-[80vh] sm:rounded-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-line sm:hidden" aria-hidden="true" />
            <div className="flex items-start justify-between px-5 pb-4 pt-4 sm:px-6 sm:pt-6">
              <div>
                <p className="text-[11px] font-bold tracking-[0.08em] text-brand">APPLICATION COACH</p>
                <h4 id="coach-modal-title" className="mt-1 flex items-center gap-2 text-[19px] font-bold tracking-tight text-ink">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-brand">
                    <CalendarDays size={17} strokeWidth={2} />
                  </span>
                  신청 일정 안내
                </h4>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">마감 전 필요한 일을 순서대로 정리했어요.</p>
              </div>
              <button
                ref={modalCloseButtonRef}
                type="button"
                onClick={() => setIsOpenCoachModal(false)}
                aria-label="신청 일정 안내 닫기"
                className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/50 hover:text-ink active:scale-95"
              >
                <X size={20} strokeWidth={2} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto border-y border-line px-5 py-5 no-scrollbar sm:px-6">
              {loadingCoach ? (
                <div className="space-y-4 animate-pulse" aria-live="polite" aria-label="신청 일정 안내를 준비하고 있습니다">
                  <div className="h-20 rounded-2xl bg-primary-soft" />
                  <div className="space-y-3 border-l border-line pl-4">
                    <div className="h-32 rounded-2xl bg-surface" />
                    <div className="h-24 rounded-2xl bg-surface" />
                  </div>
                  <p className="pt-1 text-center text-xs font-medium text-subtle">
                    등록한 일정과 신청 단계를 확인하고 있습니다.
                  </p>
                </div>
              ) : (
                <CoachGuideContent guide={coachGuide} />
              )}
            </div>

            {loadingCoach ? (
              <button
                type="button"
                disabled
                className="m-5 min-h-12 rounded-xl bg-line text-sm font-bold text-subtle cursor-not-allowed sm:m-6"
              >
                확인 중
              </button>
            ) : (
              <div className="flex gap-2.5 p-5 sm:p-6">
                <a
                  href="https://calendar.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex min-h-12 flex-1 items-center justify-center gap-1.5 rounded-xl border border-line bg-surface px-3 text-sm font-bold text-ink transition-colors hover:bg-line/30 active:scale-[0.98]"
                >
                  <CalendarDays size={15} /> 구글 캘린더 열기
                </a>
                <button
                  type="button"
                  onClick={() => setIsOpenCoachModal(false)}
                  className="min-h-12 flex-1 rounded-xl bg-ink px-3 text-sm font-bold text-white transition-colors hover:bg-ink/90 active:scale-[0.98]"
                >
                  확인했습니다
                </button>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function HomeScreenSkeleton() {
  return (
    <div className="pb-6">
      <TopBar />

      <PageIntro
        title="내 정책 달력"
        description={
          <span className="inline-flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-primary"
            />
            사용자 정보와 달력을 불러오는 중이에요
          </span>
        }
      />

      <section className="mt-4 px-5">
        <div className="surface-panel animate-pulse p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="h-6 w-28 rounded-lg bg-line/80" />
            <div className="flex gap-1">
              <div className="h-11 w-11 rounded-full bg-line/70" />
              <div className="h-11 w-11 rounded-full bg-line/70" />
            </div>
          </div>

          <div className="grid grid-cols-7 text-center">
            {WEEK.map((day) => (
              <div key={day} className="pb-2">
                <div className="mx-auto h-3 w-4 rounded bg-line/60" />
              </div>
            ))}
            {Array.from({ length: 42 }, (_, index) => (
              <div
                key={index}
                className="flex h-11 flex-col items-center justify-center"
              >
                <div className="h-8 w-8 rounded-lg bg-line/70" />
                <div className="mt-1 h-1.5 w-3 rounded-full bg-line/50" />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-3 px-5">
        <div className="h-12 animate-pulse rounded-xl border border-line bg-surface" />
      </section>

      <section className="mt-6 px-5">
        <div className="h-6 w-40 animate-pulse rounded-lg bg-line/80" />
        <div className="surface-panel mt-3 h-20 animate-pulse bg-line/30" />
      </section>
    </div>
  )
}

function DeadlineCard({ policy }: { policy: SavedPolicy }) {
  const navigate = useNavigate()
  const info = getDeadlineInfo(policy)
  // 날짜가 없으면 기간 줄을 통째로 숨긴다. "미정 ~ 미정"을 만들지 않는다.
  const period = formatPeriod(policy)
  const labels = getPolicyLabels(policy)
  const goToDetail = () => navigate(`/policy/${policy.policy_id}`)

  return (
    <article
      role="link"
      tabIndex={0}
      onClick={goToDetail}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          goToDetail()
        }
      }}
      className="cursor-pointer px-4 py-4 outline-none transition-colors hover:bg-cream/60 focus-visible:bg-cream/60 active:bg-cream"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <StatusBadge info={info} />
          <h4 className="mt-2 line-clamp-2 text-card text-ink">{policy.title}</h4>

          {labels.length > 0 && (
            <div className="mt-1.5">
              <TagList items={labels} max={2} />
            </div>
          )}

          {policy.summary && (
            <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-muted">
              {policy.summary}
            </p>
          )}
        </div>

        <ChevronRight size={18} className="mt-1 shrink-0 text-subtle" />
      </div>

      {(period || info.calendarable) && (
        <div className="mt-2.5 flex min-h-11 items-center justify-between gap-2 border-t border-line pt-2">
          {period ? <p className="text-xs font-medium text-subtle">{period}</p> : <span />}
          {/* 마감일이 없으면 캘린더에 넣을 날짜도 없다. 버튼 자체를 띄우지 않는다. */}
          {info.calendarable && (
            <div
              onClick={(event) => event.stopPropagation()}
              onKeyDown={(event) => event.stopPropagation()}
            >
              <AddToCalendarButton policyId={policy.policy_id} applyEnd={policy.apply_end} />
            </div>
          )}
        </div>
      )}
    </article>
  )
}

// 자동 정리 결과에 남은 마크다운 기호를 화면용 텍스트로 정리한다.
type CoachAction = {
  title: string
  items: string[]
}

type CoachStep = {
  day: string
  date: string | null
  label: string | null
  actions: CoachAction[]
}

function normalizeCoachLine(line: string) {
  return cleanMarkdown(line)
    .replace(/^\s{0,3}#{1,6}\s+/, '')
    .trim()
}

function isCoachDate(value: string) {
  return /(?:\d{4}\s*(?:년|[-./])\s*\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일)/.test(value)
}

function parseCoachStepHeading(line: string): Pick<CoachStep, 'day' | 'date' | 'label'> | null {
  const dayMatch = line.match(/^(D\s*(?:[-+]\s*\d+|[-\s]?DAY))\b/i)
  if (!dayMatch) return null

  const rawDay = dayMatch[1]
  const day = /DAY$/i.test(rawDay) ? 'D-Day' : rawDay.replace(/\s/g, '').toUpperCase()
  let rest = line.slice(dayMatch[0].length).trim()
  let date: string | null = null
  const labels: string[] = []

  while (rest.startsWith('(')) {
    const closingIndex = rest.indexOf(')')
    if (closingIndex === -1) break

    const value = rest.slice(1, closingIndex).trim()
    if (value) {
      if (!date && isCoachDate(value)) date = value
      else labels.push(value)
    }
    rest = rest.slice(closingIndex + 1).trim()
  }

  rest = rest.replace(/^(?:[-\u2013\u2014:|])\s*/, '').trim()
  if (rest) labels.push(rest)

  return { day, date, label: labels.join(' · ') || null }
}

function parseCoachGuide(text: string | null): { intro: string[]; steps: CoachStep[]; fallback: string[] } {
  const lines = (text ?? '')
    .split('\n')
    .map(normalizeCoachLine)
    .filter(Boolean)

  const intro: string[] = []
  const steps: CoachStep[] = []
  let currentStep: CoachStep | null = null
  let currentAction: CoachAction | null = null

  for (const line of lines) {
    const stepHeading = parseCoachStepHeading(line)
    if (stepHeading) {
      currentStep = {
        ...stepHeading,
        actions: [],
      }
      steps.push(currentStep)
      currentAction = null
      continue
    }

    if (!currentStep) {
      intro.push(line)
      continue
    }

    const actionMatch = line.match(/^\s*(\d+)[.)]\s+(.+)$/)
    if (actionMatch) {
      currentAction = { title: actionMatch[2], items: [] }
      currentStep.actions.push(currentAction)
      continue
    }

    const itemMatch = line.match(/^\s*[•·*-]\s+(.+)$/)
    if (itemMatch && currentAction) {
      currentAction.items.push(itemMatch[1])
      continue
    }

    if (currentAction) {
      currentAction.title = `${currentAction.title} ${line}`
    } else {
      currentAction = { title: line, items: [] }
      currentStep.actions.push(currentAction)
    }
  }

  return { intro, steps, fallback: lines }
}

function CoachGuideContent({ guide }: { guide: string | null }) {
  const { intro, steps, fallback } = parseCoachGuide(guide)
  const introText = intro
    .map((line) => line.replace(/^한\s*줄?\s*요약[:：]\s*/, '').trim())
    .filter(Boolean)
    .join(' ')

  if (steps.length === 0) {
    return <div className="whitespace-pre-line text-sm leading-7 text-muted">{fallback.join('\n')}</div>
  }

  return (
    <div className="space-y-5">
      {introText && (
        <div className="rounded-2xl border border-primary/10 bg-primary-soft/70 p-4">
          <p className="text-[11px] font-bold tracking-[0.08em] text-primary">이번 신청 전략</p>
          <p className="mt-1.5 text-sm leading-6 text-ink">{introText}</p>
        </div>
      )}

      <ol className="space-y-3 border-l border-brand/20 pl-4">
        {steps.map((step) => (
          <li key={`${step.day}-${step.date ?? ''}-${step.label ?? ''}`} className="relative">
            <span className="absolute -left-[23px] top-5 h-3 w-3 rounded-full border-[3px] border-cream bg-brand" aria-hidden="true" />
            <article className="overflow-hidden rounded-2xl border border-line bg-surface">
              <header className="flex items-center gap-2.5 border-b border-line bg-cream/60 px-4 py-3">
                <span className="inline-flex rounded-md bg-ink px-2 py-1 text-xs font-bold tabular-nums text-white">
                  {step.day}
                </span>
                <div className="min-w-0">
                  <h5 className="text-sm font-bold text-ink">{step.label ?? '신청 준비'}</h5>
                  {step.date && <p className="mt-0.5 text-xs font-medium text-muted">{step.date}</p>}
                </div>
              </header>
              <div className="space-y-4 p-4">
                {step.actions.map((action, actionIndex) => (
                  <div key={`${action.title}-${actionIndex}`} className="flex gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11px] font-bold tabular-nums text-brand">
                      {String(actionIndex + 1).padStart(2, '0')}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-6 text-ink">{action.title}</p>
                      {action.items.length > 0 && (
                        <ul className="mt-2 space-y-1.5 border-l border-line pl-3">
                          {action.items.map((item) => (
                            <li key={item} className="flex items-start gap-2 text-[13px] leading-5 text-muted">
                              <CheckCircle2 size={14} strokeWidth={1.8} className="mt-0.5 shrink-0 text-brand" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </li>
        ))}
      </ol>
    </div>
  )
}

function cleanMarkdown(text: string | null): string {
  if (!text) return ''
  return text
    .replace(/###\s*(.*)/g, '$1')     // '### 제목' -> '제목' (샵 제거)
    .replace(/##\s*(.*)/g, '$1')      // '## 제목' -> '제목'
    .replace(/#\s*(.*)/g, '$1')       // '# 제목' -> '제목'
    .replace(/\*\*(.*?)\*\*/g, '$1')  // '**강조**' -> '강조' (별표 제거)
    .replace(/\*(.*?)\*/g, '$1')      // '*이탤릭*' -> '이탤릭'
    .replace(/^\s*-\s+/gm, '• ')      // '- 리스트' -> '• 리스트' (대시를 동그라미 불릿으로 변환)
    .replace(/\{[^{}]+\}/g, '')       // [이재혁] '{...}' 형태의 원시 JSON/딕셔너리 코드 블록 제거
    .replace(/\(\s*예:\s*\)/g, '')    // [이재혁] 남겨진 빈 예시 괄호 '(예: )' 정리
    .replace(/`([^`]+)`/g, '$1')      // '`코드`' -> '코드'
}
