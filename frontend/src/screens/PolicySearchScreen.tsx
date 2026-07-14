import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Sparkles } from 'lucide-react'
import TopBar from '../components/TopBar'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import { apiFetch, ApiError } from '../lib/api'
import { buildRecommendationRequest, NEED_OPTIONS, REGION_MAP } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type { RecommendationPreviewResponse, SavedPolicy } from '../types'

type Tab = 'recommend' | 'saved' | 'all'
type AllSort = 'deadline' | 'latest'
type AllStatus = 'available' | 'all'

const ALL_PAGE_SIZE = 12
const ALL_SIDO_OPTIONS = ['전체', ...Object.keys(REGION_MAP)]

// 추천을 기본 진입 탭으로 둔다. 앱의 핵심 가치이고, '정책 찾기'를 눌렀을 때
// 수천 건의 전체 목록보다 맞춤 몇 건을 먼저 보는 게 자연스럽다.
// 이모지를 뺐다. 짧은 한글 라벨 셋에 아이콘을 붙이면 소음만 는다.
const TABS: { key: Tab; label: string }[] = [
  { key: 'recommend', label: '추천' },
  { key: 'saved', label: '저장한' },
  { key: 'all', label: '전체' },
]

/** 전체 정책 목록 API 응답 */
interface NormalizedPolicyListItem {
  id: string
  title: string
  summary?: string | null
  support_type?: string | null
  apply_end?: string | null
  /** open | notice | closed — '상시 접수'와 '기간 확인 필요'를 가른다 */
  status?: string | null
  categories: string[]
}

interface NormalizedPolicyListResponse {
  items: NormalizedPolicyListItem[]
  total: number
  skip: number
  limit: number
  has_next: boolean
}

export default function PolicySearchScreen() {
  const [tab, setTab] = useState<Tab>('recommend')
  const { profile, loading: profileLoading } = useProfile()
  const { policies: saved, has, toggle, loading: savedLoading, reload: reloadSaved } = useSavedPolicies()

  const [recommendations, setRecommendations] = useState<PolicyCardData[]>([])
  const [recMeta, setRecMeta] = useState<{ total: number; returned: number } | null>(null)
  const [recLoading, setRecLoading] = useState(false)
  const [recError, setRecError] = useState<string | null>(null)

  const [all, setAll] = useState<PolicyCardData[]>([])
  const [allMeta, setAllMeta] = useState<Pick<NormalizedPolicyListResponse, 'total' | 'has_next'> | null>(null)
  const [allLoading, setAllLoading] = useState(false)
  const [allError, setAllError] = useState<string | null>(null)
  const [allCategory, setAllCategory] = useState('')
  const [allSido, setAllSido] = useState('')
  const [allStatus, setAllStatus] = useState<AllStatus>('available')
  const [allSort, setAllSort] = useState<AllSort>('deadline')
  const [allPage, setAllPage] = useState(0)
  const [allPageInput, setAllPageInput] = useState('1')
  const [savedCategory, setSavedCategory] = useState('')
  const [savedSido, setSavedSido] = useState('')
  const [savedStatus, setSavedStatus] = useState<AllStatus>('available')
  const [savedSort, setSavedSort] = useState<AllSort>('deadline')

  const [pendingSave, setPendingSave] = useState<string | null>(null)

  const loadRecommendations = useCallback(async () => {
    setRecLoading(true)
    setRecError(null)
    try {
      const data = await apiFetch<RecommendationPreviewResponse>(
        '/api/v1/recommend/preview?limit=10',
        { method: 'POST', json: buildRecommendationRequest(profile) },
      )
      setRecMeta({ total: data.total_candidates, returned: data.returned })
      setRecommendations(
        data.results.map((item) => ({
          policy_id: item.policy_id,
          title: item.title,
          summary: item.summary,
          support_type: item.support_type,
          apply_end: item.apply_end,
          status: item.status,
          rank_score: item.rank_score,
          match_status: item.match_status,
          reasons: item.reasons,
          warnings: item.warnings,
        })),
      )
    } catch {
      setRecError('추천을 불러오지 못했습니다.')
    } finally {
      setRecLoading(false)
    }
  }, [profile])

  const loadAll = useCallback(async () => {
    setAllLoading(true)
    setAllError(null)
    const params = new URLSearchParams({
      skip: String(allPage * ALL_PAGE_SIZE),
      limit: String(ALL_PAGE_SIZE),
      status: allStatus,
      sort: allSort,
    })
    if (allCategory) params.set('category', allCategory)
    if (allSido) params.set('sido', allSido)

    try {
      const data = await apiFetch<NormalizedPolicyListResponse>(
        `/api/v1/policies/normalized/?${params.toString()}`,
      )
      setAll(
        data.items.map((p) => ({
          policy_id: p.id,
          title: p.title,
          summary: p.summary,
          support_type: p.support_type,
          apply_end: p.apply_end,
          // status가 있어야 '상시 접수'와 '기간 확인 필요'를 가를 수 있다.
          status: p.status,
          categories: p.categories,
        })),
      )
      setAllMeta({ total: data.total, has_next: data.has_next })
    } catch (error) {
      setAllError(
        error instanceof ApiError && error.status === 404
          ? '전체 정책 조회 API가 아직 배포되지 않았어요.'
          : '전체 정책을 불러오지 못했어요. 잠시 후 다시 시도해주세요.',
      )
      setAll([])
      setAllMeta(null)
    } finally {
      setAllLoading(false)
    }
  }, [allCategory, allPage, allSido, allSort, allStatus])

  useEffect(() => {
    setAllPageInput(String(allPage + 1))
  }, [allPage])

  useEffect(() => {
    if (profileLoading) return
    if (tab === 'recommend' && recommendations.length === 0 && !recError) loadRecommendations()
    if (tab === 'all') loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, profileLoading, loadAll])

  const handleToggleSave = async (policyId: string) => {
    setPendingSave(policyId)
    try {
      await toggle(policyId)
    } finally {
      setPendingSave(null)
    }
  }

  const savedCards: PolicyCardData[] = [...saved]
    .filter((policy) => !savedCategory || policy.categories?.includes(savedCategory))
    .filter(
      (policy) =>
        !savedSido || policy.sido === savedSido || policy.region_scope === 'national',
    )
    .filter((policy) => savedStatus === 'all' || isSavedPolicyAvailable(policy))
    .sort((left, right) => compareSavedPolicies(left, right, savedSort))
    .map((p) => ({
      policy_id: p.policy_id,
      title: p.title,
      summary: p.summary,
      support_type: p.support_type,
      apply_end: p.apply_end,
      status: p.status,
      categories: p.categories,
    }))
  const allPageCount = allMeta ? Math.max(1, Math.ceil(allMeta.total / ALL_PAGE_SIZE)) : 0
  const goToAllPage = () => {
    const requestedPage = Number.parseInt(allPageInput, 10)
    const safePage = Number.isFinite(requestedPage)
      ? Math.min(Math.max(requestedPage, 1), allPageCount || 1)
      : allPage + 1
    setAllPageInput(String(safePage))
    setAllPage(safePage - 1)
  }

  return (
    <div className="pb-6">
      <TopBar />

      <section className="px-5">
        <h2 className="text-title text-ink">정책 찾기</h2>

        {/* 세그먼트 탭 */}
        <div className="mt-4 flex gap-1 rounded-2xl bg-line/60 p-1">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition-colors ${
                tab === key ? 'bg-white text-ink shadow-card' : 'text-subtle'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-5 px-5">
        {tab === 'recommend' && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted">
                {recMeta
                  ? `${recMeta.total}개 후보 중 ${recMeta.returned}개를 골랐어요.`
                  : '내 정보 기준으로 정책을 찾는 중이에요.'}
              </p>
              <button
                onClick={loadRecommendations}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-ink shadow-card active:scale-[0.97]"
                aria-label="추천 새로고침"
              >
                <RefreshCw size={16} className={recLoading ? 'animate-spin' : ''} />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {recError && <ErrorBox message={recError} />}
              {!recError && recLoading && <InfoBox message="맞춤 정책을 계산하고 있어요." />}
              {!recLoading &&
                !recError &&
                recommendations.map((policy) => (
                  <PolicyCard
                    key={policy.policy_id}
                    policy={policy}
                    saved={has(policy.policy_id)}
                    savePending={pendingSave === policy.policy_id}
                    onToggleSave={handleToggleSave}
                  />
                ))}
              {!recLoading && !recError && recommendations.length === 0 && (
                <InfoBox message="조건에 맞는 정책을 찾지 못했어요. 마이페이지에서 정보를 수정해보세요." />
              )}
            </div>
          </>
        )}

        {tab === 'saved' && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-white p-3 shadow-card">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-ink">저장한 정책 {savedCards.length}개</p>
                <span className="text-xs text-subtle">마감된 정책은 기본으로 숨겨요</span>
              </div>
              <p className="mt-3 text-xs font-semibold text-muted">지원 분야</p>
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <CategoryChip
                  active={!savedCategory}
                  label="전체 분야"
                  onClick={() => setSavedCategory('')}
                />
                {NEED_OPTIONS.map((option) => (
                  <CategoryChip
                    key={option.tag}
                    active={savedCategory === option.tag}
                    label={option.label}
                    onClick={() => setSavedCategory(option.tag)}
                  />
                ))}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <label className="text-xs font-semibold text-muted">
                  지역
                  <select
                    value={savedSido || '전체'}
                    onChange={(event) => {
                      const value = event.target.value
                      setSavedSido(value === '전체' ? '' : value)
                    }}
                    className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink outline-none"
                  >
                    {ALL_SIDO_OPTIONS.map((sido) => (
                      <option key={sido} value={sido}>
                        {sido}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-muted">
                  보기
                  <select
                    value={savedSort}
                    onChange={(event) => setSavedSort(event.target.value as AllSort)}
                    className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink outline-none"
                  >
                    <option value="deadline">마감 임박순</option>
                    <option value="latest">최근 저장순</option>
                  </select>
                </label>
              </div>

              <label className="mt-3 flex items-center gap-2 text-sm font-medium text-ink/65">
                <input
                  type="checkbox"
                  checked={savedStatus === 'all'}
                  onChange={(event) => setSavedStatus(event.target.checked ? 'all' : 'available')}
                  className="h-4 w-4 accent-brand"
                />
                마감된 정책도 보기
              </label>
            </div>

            {savedLoading && <InfoBox message="저장한 정책을 불러오는 중이에요." />}
            {!savedLoading && savedCards.length === 0 && (
              <EmptyBox
                title="아직 저장한 정책이 없어요"
                description="추천 탭에서 마음에 드는 정책을 저장하면 홈 달력에 마감일이 표시돼요."
                actionLabel="추천 보러가기"
                onAction={() => setTab('recommend')}
              />
            )}
            {!savedLoading && saved.length > 0 && savedCards.length === 0 && (
              <InfoBox message="선택한 조건으로 저장한 정책이 없어요. 다른 필터를 선택해보세요." />
            )}
            {savedCards.map((policy) => (
              <PolicyCard
                key={policy.policy_id}
                policy={policy}
                saved
                savePending={pendingSave === policy.policy_id}
                onToggleSave={handleToggleSave}
              />
            ))}
          </div>
        )}

        {tab === 'all' && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-white p-3 shadow-card">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-ink">
                  {allMeta ? `${allMeta.total}개 정책` : '전체 정책'}
                </p>
                <span className="text-xs text-subtle">마감된 정책은 기본으로 숨겨요</span>
              </div>

              <p className="mt-3 text-xs font-semibold text-muted">지원 분야</p>
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <CategoryChip
                  active={!allCategory}
                  label="전체 분야"
                  onClick={() => {
                    setAllCategory('')
                    setAllPage(0)
                  }}
                />
                {NEED_OPTIONS.map((option) => (
                  <CategoryChip
                    key={option.tag}
                    active={allCategory === option.tag}
                    label={option.label}
                    onClick={() => {
                      setAllCategory(option.tag)
                      setAllPage(0)
                    }}
                  />
                ))}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <label className="text-xs font-semibold text-muted">
                  지역
                  <select
                    value={allSido || '전체'}
                    onChange={(event) => {
                      const value = event.target.value
                      setAllSido(value === '전체' ? '' : value)
                      setAllPage(0)
                    }}
                    className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink outline-none"
                  >
                    {ALL_SIDO_OPTIONS.map((sido) => (
                      <option key={sido} value={sido}>
                        {sido}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-muted">
                  보기
                  <select
                    value={allSort}
                    onChange={(event) => {
                      setAllSort(event.target.value as AllSort)
                      setAllPage(0)
                    }}
                    className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink outline-none"
                  >
                    <option value="deadline">마감 임박순</option>
                    <option value="latest">최신 등록순</option>
                  </select>
                </label>
              </div>

              <label className="mt-3 flex items-center gap-2 text-sm font-medium text-ink/65">
                <input
                  type="checkbox"
                  checked={allStatus === 'all'}
                  onChange={(event) => {
                    setAllStatus(event.target.checked ? 'all' : 'available')
                    setAllPage(0)
                  }}
                  className="h-4 w-4 accent-brand"
                />
                마감된 정책도 보기
              </label>
            </div>

            {allLoading && <InfoBox message="전체 정책을 불러오는 중이에요." />}
            {allError && <ErrorBox message={allError} />}
            {!allLoading &&
              !allError &&
              all.map((policy) => (
                <PolicyCard
                  key={policy.policy_id}
                  policy={policy}
                  saved={has(policy.policy_id)}
                  savePending={pendingSave === policy.policy_id}
                  onToggleSave={handleToggleSave}
                />
              ))}
            {!allLoading && !allError && all.length === 0 && (
              <InfoBox message="조건에 맞는 정책이 없어요. 다른 분야나 지역을 선택해보세요." />
            )}
            {!allLoading && !allError && allMeta && allMeta.total > 0 && (
              <div className="flex items-center justify-between gap-2 pt-1">
                <button
                  type="button"
                  disabled={allPage === 0}
                  onClick={() => setAllPage((page) => page - 1)}
                  aria-label="이전 페이지"
                  className="shrink-0 rounded-xl bg-white px-3 py-2.5 text-sm font-bold text-ink shadow-card disabled:opacity-30"
                >
                  이전
                </button>
                <div className="flex min-w-0 items-center justify-center gap-1.5">
                  <label htmlFor="all-page-input" className="sr-only">
                    이동할 페이지
                  </label>
                  <input
                    id="all-page-input"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={allPageCount}
                    value={allPageInput}
                    onChange={(event) => setAllPageInput(event.target.value.replace(/[^0-9]/g, ''))}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') goToAllPage()
                    }}
                    className="h-9 w-14 rounded-lg border border-line bg-white px-2 text-center text-sm font-bold text-ink outline-none focus:border-primary"
                  />
                  <span className="whitespace-nowrap text-sm font-semibold text-muted">
                    / {allPageCount}페이지
                  </span>
                  <button
                    type="button"
                    onClick={goToAllPage}
                    className="h-9 rounded-lg bg-black/[0.05] px-2.5 text-xs font-bold text-ink"
                  >
                    이동
                  </button>
                </div>
                <button
                  type="button"
                  disabled={!allMeta.has_next || allPage + 1 >= allPageCount}
                  onClick={() => setAllPage((page) => page + 1)}
                  aria-label="다음 페이지"
                  className="shrink-0 rounded-xl bg-primary px-3 py-2.5 text-sm font-bold text-white disabled:opacity-30"
                >
                  다음
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      {/* 저장 목록이 바뀌면 홈 달력도 갱신되도록, 탭 전환 시 서버와 다시 맞춘다 */}
      <RefetchOnTab tab={tab} onSavedTab={reloadSaved} />
    </div>
  )
}

function RefetchOnTab({ tab, onSavedTab }: { tab: Tab; onSavedTab: () => void }) {
  useEffect(() => {
    if (tab === 'saved') onSavedTab()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])
  return null
}

function InfoBox({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 text-sm font-medium text-muted shadow-card">
      {message}
    </div>
  )
}

function CategoryChip({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex min-h-10 w-full items-center justify-center rounded-xl px-2 py-2 text-center text-xs font-bold transition-colors ${
        active ? 'bg-primary text-white' : 'bg-line/60 text-muted'
      }`}
    >
      {label}
    </button>
  )
}

function isSavedPolicyAvailable(policy: SavedPolicy) {
  if (policy.status === 'closed') return false
  const applyEnd = toTimestamp(policy.apply_end)
  return applyEnd === null || applyEnd >= Date.now()
}

function compareSavedPolicies(left: SavedPolicy, right: SavedPolicy, sort: AllSort) {
  if (sort === 'latest') {
    return (toTimestamp(right.saved_at) ?? 0) - (toTimestamp(left.saved_at) ?? 0)
  }

  const statusRank: Record<string, number> = { open: 0, notice: 1, closed: 2 }
  const statusDifference = (statusRank[left.status || ''] ?? 3) - (statusRank[right.status || ''] ?? 3)
  if (statusDifference !== 0) return statusDifference

  const leftEnd = toTimestamp(left.apply_end)
  const rightEnd = toTimestamp(right.apply_end)
  if (leftEnd === null && rightEnd !== null) return 1
  if (leftEnd !== null && rightEnd === null) return -1
  if (leftEnd !== null && rightEnd !== null && leftEnd !== rightEnd) return leftEnd - rightEnd
  return (toTimestamp(right.saved_at) ?? 0) - (toTimestamp(left.saved_at) ?? 0)
}

function toTimestamp(value: string | null | undefined) {
  if (!value) return null
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? null : timestamp
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 text-sm font-medium text-status-red shadow-card">
      {message}
    </div>
  )
}

function EmptyBox({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string
  description: string
  actionLabel: string
  onAction: () => void
}) {
  return (
    <div className="rounded-3xl bg-white p-6 text-center shadow-card">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft">
        <Sparkles size={22} className="text-accent" />
      </div>
      <h3 className="mt-4 text-section text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
      <button
        onClick={onAction}
        className="mt-5 w-full rounded-2xl bg-primary py-3 text-sm font-bold text-white active:scale-[0.99]"
      >
        {actionLabel}
      </button>
    </div>
  )
}
