import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, Compass, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import TopBar from '../components/TopBar'
import { Button, EmptyState, IconButton, LoadingLine, StatusBadge } from '../components/ui'
import { toDateKey } from '../lib/calendar'
import { getDeadlineInfo, formatPeriod, type DeadlineKind } from '../lib/deadline'
import { TODAY } from '../lib/format'
import { useSavedPolicies } from '../lib/storage'
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

  const todayDate = new Date(`${TODAY}T00:00:00`)
  const [cursor, setCursor] = useState({
    year: todayDate.getFullYear(),
    month: todayDate.getMonth(),
  })
  const [selected, setSelected] = useState(TODAY)

  // [이재혁 - 실시간 구글 캘린더 개인 일정 연동 상태]
  const [googleEvents, setGoogleEvents] = useState<{ date: string; time: string | null; summary: string; policy_id: string | null }[]>([])

  useEffect(() => {
    let ignore = false
    
    // 기본 패치 헬퍼
    const fetchEvents = () => {
      apiFetch<{ date: string; time: string | null; summary: string; policy_id: string | null }[]>('/api/v1/calendar/events')
        .then((data) => {
          if (!ignore) {
            setGoogleEvents(data)
            sessionStorage.removeItem('sobok_calendar_dirty')
          }
        })
        .catch((err) => {
          console.warn('구글 캘린더 일정을 조회할 수 없습니다 (인증 필요):', err)
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

  // [이재혁 - 홈 화면 즉시 AI 코칭 연동 상태]
  const [coachGuide, setCoachGuide] = useState<string | null>(null)
  const [loadingCoach, setLoadingCoach] = useState(false)
  const [isOpenCoachModal, setIsOpenCoachModal] = useState(false)

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

  // [이재혁 - 홈 화면 AI 일정 코치 비동기 호출 헬퍼]
  const handleCoachTimeline = async () => {
    const selGoogleEvents = googleEventsMap[selected] || []
    
    // 1순위: 선택한 날짜의 구글 일정(파란 점) 중 본문에 매핑된 지원사업 ID가 있는 일정을 역추적해 타겟팅
    const calendarTarget = selGoogleEvents.find(ev => ev.policy_id)
    
    let targetPolicyId: string | null = null
    
    if (calendarTarget?.policy_id) {
      targetPolicyId = calendarTarget.policy_id
    } else {
      // 2순위 Fallback: 선택한 날짜에 마감 공고가 없더라도, 현재 구글 캘린더 전체 일정 중 policy_id가 박힌 연동 마감 일정들을 역추적
      const calendarPolicies = googleEvents.filter(ev => ev.policy_id)
      if (calendarPolicies.length === 0) {
        alert('아직 구글 캘린더에 연동된 일정(파란 점)이 없어요! 상세페이지에서 [캘린더에 연동하기] 버튼을 먼저 눌러 일정을 등록해 주세요.')
        return
      }
      // 연동된 구글 일정 중 마감일이 가장 시급한 녀석을 타겟으로 자동 지정
      const urgentCalendarTarget = [...calendarPolicies].sort((a, b) => {
        const da = new Date(a.date).getTime()
        const db = new Date(b.date).getTime()
        return da - db
      })[0]
      targetPolicyId = urgentCalendarTarget.policy_id
    }

    if (!targetPolicyId) return
    if (loadingCoach) return
    setCoachGuide(null) // 기존 코칭 가이드 텍스트 리셋
    setIsOpenCoachModal(true) // 즉각 모달을 먼저 띄움!
    setLoadingCoach(true)
    try {
      const data = await apiFetch<{ coach_guide: string }>(`/api/v1/calendar/coach?policy_id=${targetPolicyId}&target_date=${selected}`)
      setCoachGuide(data.coach_guide)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'AI 코칭 일정을 불러오지 못했어요. 구글 연동 상태를 확인해 주세요.')
      setIsOpenCoachModal(false) // 에러 시 모달 닫기
    } finally {
      setLoadingCoach(false)
    }
  }
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
                    {hasGoogle && (
                      <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                    )}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* [이재혁 - 홈 화면 즉시 AI 코칭 버튼] */}
      <section className="mt-3 px-5">
        <Button
          onClick={handleCoachTimeline}
          disabled={loadingCoach}
          full
        >
          {loadingCoach ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
          ) : (
            <Sparkles size={16} className="text-white fill-white/10" />
          )}
          &nbsp;소복이 AI 스케줄 코칭받기
        </Button>
      </section>

      {/* 선택한 날짜 */}
      <section className="mt-6 px-5">
        <h3 className="text-section text-ink">
          {selDate.getMonth() + 1}월 {selDate.getDate()}일 마감
        </h3>

        <div className="mt-3 space-y-2.5">
          {/* [이재혁 - 실시간 구글 캘린더 개인 일정 연동 리스트] */}
          {(() => {
            const selGoogleEvents = googleEventsMap[selected] || []
            const hasNoEvents = dayList.length === 0 && selGoogleEvents.length === 0

            return (
              <>
                {selGoogleEvents.length > 0 && (
                  <div className="mb-3 space-y-2">
                    {selGoogleEvents.map((ev, i) => (
                      <div key={i} className="flex items-center gap-3 rounded-2xl bg-blue-50/70 p-4 border border-blue-100/60 shadow-card">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600">
                          <CalendarDays size={16} />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold text-blue-500 uppercase tracking-wider">구글 캘린더 일정</span>
                            {ev.time && (
                              <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-bold text-blue-600">
                                {ev.time}
                              </span>
                            )}
                          </div>
                          <p className="text-sm font-semibold text-ink leading-snug mt-0.5">{ev.summary}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {hasNoEvents ? (
                  <p className="rounded-2xl bg-surface px-4 py-5 text-center text-sm text-subtle shadow-card">
                    이 날 등록된 일정이 없어요
                  </p>
                ) : (
                  dayList.map((policy) => <DeadlineCard key={policy.policy_id} policy={policy} />)
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

      {/* [이재혁 - 홈 화면 즉시 AI 코칭 모달 팝업] */}
      {isOpenCoachModal && (coachGuide || loadingCoach) && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-0 sm:p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-t-3xl sm:rounded-2xl bg-cream p-6 shadow-2xl max-h-[80vh] flex flex-col overflow-hidden border border-line">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <h4 className="text-base font-bold text-ink flex items-center gap-1.5">
                <Sparkles size={18} className="text-brand fill-brand/10" /> 소복이 AI 일정 코칭
              </h4>
              <button 
                type="button"
                onClick={() => setIsOpenCoachModal(false)}
                className="text-sm font-semibold text-muted hover:text-ink active:scale-95"
              >
                닫기
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto mt-4 text-[14px] leading-relaxed text-ink/80 whitespace-pre-line pr-1 no-scrollbar">
              {loadingCoach ? (
                <div className="space-y-4 animate-pulse py-2">
                  <div className="h-4 bg-line/80 rounded-lg w-3/4" />
                  <div className="space-y-2 mt-4">
                    <div className="h-3 bg-line/60 rounded-md w-full" />
                    <div className="h-3 bg-line/60 rounded-md w-5/6" />
                    <div className="h-3 bg-line/60 rounded-md w-4/5" />
                  </div>
                  <div className="h-4 bg-line/80 rounded-lg w-1/2 mt-6" />
                  <div className="space-y-2 mt-3">
                    <div className="h-3 bg-line/60 rounded-md w-full" />
                    <div className="h-3 bg-line/60 rounded-md w-2/3" />
                  </div>
                  <p className="text-center text-xs text-subtle font-medium mt-6 pt-4 border-t border-line/40">
                    소복이 AI가 사장님의 구글 일정과 대조해<br />스케줄을 치밀하게 분석하고 있어요... 🤖✍️
                  </p>
                </div>
              ) : (
                cleanMarkdown(coachGuide)
              )}
            </div>
            
            {loadingCoach ? (
              <button
                type="button"
                disabled
                className="mt-5 w-full rounded-xl bg-line py-3 text-sm font-bold text-subtle cursor-not-allowed"
              >
                분석 중...
              </button>
            ) : (
              <div className="mt-5 flex gap-3">
                <a
                  href="https://calendar.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-line bg-white py-3 text-sm font-bold text-ink hover:bg-line/20 active:scale-[0.98] transition-transform"
                >
                  📅 구글 캘린더 열기
                </a>
                <button
                  type="button"
                  onClick={() => setIsOpenCoachModal(false)}
                  className="flex-1 rounded-xl bg-ink py-3 text-sm font-bold text-white hover:opacity-90 active:scale-[0.98] transition-transform"
                >
                  확인했습니다
                </button>
              </div>
            )}
          </div>
        </div>
      )}
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

// [이재혁 - AI 출력값 마크다운 특수기호 세탁 헬퍼]
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
