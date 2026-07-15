import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Search, X } from 'lucide-react'
import TopBar from '../components/TopBar'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import { ChoiceChip, EmptyState, Notice, PageIntro, Pagination } from '../components/ui'
import { apiFetch, ApiError } from '../lib/api'
import { buildRecommendationRequest, NEED_OPTIONS, REGION_MAP } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type { RecommendationPreviewResponse, SavedPolicy } from '../types'

type Tab = 'recommend' | 'saved' | 'all'
type AllSort = 'deadline' | 'latest'
type AllStatus = 'available' | 'all'
type RecommendationStatus = 'eligible' | 'needs_review' | 'near_match'

const ALL_PAGE_SIZE = 12
const RECOMMENDATION_PAGE_SIZE = ALL_PAGE_SIZE
const ALL_SIDO_OPTIONS = ['전체', ...Object.keys(REGION_MAP)]
const RECOMMENDATION_FILTERS: { key: RecommendationStatus; label: string }[] = [
  { key: 'eligible', label: '바로 확인 가능' },
  { key: 'needs_review', label: '조건 확인 필요' },
  { key: 'near_match', label: '유사 정책' },
]

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
  const [recMeta, setRecMeta] = useState<{
    total: number
    filtered: number
    returned: number
    hasNext: boolean
    statusCounts: RecommendationPreviewResponse['status_counts']
  } | null>(null)
  // 아무 상태도 선택하지 않으면 전체 추천을 보여준다. 여러 상태를 동시에
  // 선택하면 선택한 상태들의 합집합을 한 목록으로 보여준다.
  const [recFilters, setRecFilters] = useState<RecommendationStatus[]>([])
  const [recPage, setRecPage] = useState(0)
  const [recPageInput, setRecPageInput] = useState('1')
  const [profileWarnings, setProfileWarnings] = useState<string[]>([])
  const [recLoading, setRecLoading] = useState(false)
  const [recError, setRecError] = useState<string | null>(null)

  const [all, setAll] = useState<PolicyCardData[]>([])
  const [allMeta, setAllMeta] = useState<Pick<NormalizedPolicyListResponse, 'total' | 'has_next'> | null>(null)
  const [allLoading, setAllLoading] = useState(false)
  const [allError, setAllError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [allQuery, setAllQuery] = useState('')
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
    setProfileWarnings([])
    const params = new URLSearchParams({
      skip: String(recPage * RECOMMENDATION_PAGE_SIZE),
      limit: String(RECOMMENDATION_PAGE_SIZE),
    })
    if (recFilters.length === 0) {
      params.set('status', 'all')
    } else {
      recFilters.forEach((filter) => params.append('status', filter))
    }
    try {
      const data = await apiFetch<RecommendationPreviewResponse>(
        `/api/v1/recommend/preview?${params.toString()}`,
        { method: 'POST', json: buildRecommendationRequest(profile) },
      )
      setRecMeta({
        total: data.total_candidates,
        filtered: data.filtered_candidates,
        returned: data.returned,
        hasNext: data.has_next,
        statusCounts: data.status_counts,
      })
      setProfileWarnings(data.profile_warnings || [])
      setRecommendations(
        data.results.map((item) => ({
          policy_id: item.policy_id,
          title: item.title,
          summary: item.summary,
          support_type: item.support_type,
          apply_end: item.apply_end,
          status: item.status,
          rank_score: item.rank_score,
          eligibility_status: item.eligibility_status,
          preference_match: item.preference_match,
          match_status: item.match_status,
          reasons: item.reasons,
          warnings: item.warnings,
          unmet_conditions: item.unmet_conditions,
        })),
      )
    } catch (error) {
      setRecError(error instanceof Error ? error.message : '추천을 불러오지 못했습니다.')
    } finally {
      setRecLoading(false)
    }
  }, [profile, recFilters, recPage])

  const loadAll = useCallback(async () => {
    setAllLoading(true)
    setAllError(null)
    const params = new URLSearchParams({
      skip: String(allPage * ALL_PAGE_SIZE),
      limit: String(ALL_PAGE_SIZE),
      status: allStatus,
      sort: allSort,
    })
    if (allQuery) params.set('q', allQuery)
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
  }, [allCategory, allPage, allQuery, allSido, allSort, allStatus])

  useEffect(() => {
    setRecPageInput(String(recPage + 1))
    setAllPageInput(String(allPage + 1))
  }, [allPage, recPage])

  useEffect(() => {
    if (profileLoading) return
    if (tab === 'recommend') loadRecommendations()
    if (tab === 'all') loadAll()
  }, [tab, profileLoading, loadAll, loadRecommendations])

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
  const recPageCount = recMeta ? Math.max(1, Math.ceil(recMeta.filtered / RECOMMENDATION_PAGE_SIZE)) : 0
  const goToRecommendationPage = () => {
    const requestedPage = Number.parseInt(recPageInput, 10)
    const safePage = Number.isFinite(requestedPage)
      ? Math.min(Math.max(requestedPage, 1), recPageCount || 1)
      : recPage + 1
    setRecPageInput(String(safePage))
    setRecPage(safePage - 1)
  }

  const goToAllPage = () => {
    const requestedPage = Number.parseInt(allPageInput, 10)
    const safePage = Number.isFinite(requestedPage)
      ? Math.min(Math.max(requestedPage, 1), allPageCount || 1)
      : allPage + 1
    setAllPageInput(String(safePage))
    setAllPage(safePage - 1)
  }

  const runPolicySearch = () => {
    const query = searchInput.trim()
    setSearchInput(query)
    setAllQuery(query)
    setAllMeta(null)
    setAllPage(0)
    setTab('all')
  }

  const clearPolicySearch = () => {
    setSearchInput('')
    setAllQuery('')
    setAllMeta(null)
    setAllPage(0)
    setTab('all')
  }

  return (
    <div className="pb-6">
      <TopBar />

      <PageIntro title="정책 찾기" />

      <section className="px-5">
        {/* 세그먼트 탭 — 밑줄형.
            알약형(배경 채운 것)은 그 자체가 한 덩어리로 튀어서, 정작 아래 목록보다
            먼저 눈에 들어온다. 탭은 길잡이지 주인공이 아니다. */}
        <div className="mt-4 flex border-b border-line">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`relative h-11 flex-1 rounded-t-lg text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30 ${
                tab === key ? 'font-bold text-ink' : 'font-medium text-muted hover:text-ink'
              }`}
            >
              {label}
              {tab === key && (
                <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-primary" />
              )}
            </button>
          ))}
        </div>

        <form
          role="search"
          className="mt-3"
          onSubmit={(event) => {
            event.preventDefault()
            runPolicySearch()
          }}
        >
          <div className="relative">
            <Search
              size={18}
              aria-hidden="true"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle"
            />
            <input
              type="text"
              inputMode="search"
              enterKeyHint="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="정책명이나 지원 내용 검색"
              aria-label="정책 검색어"
              className="h-12 w-full rounded-xl border border-line bg-surface pl-10 pr-24 text-sm font-medium text-ink outline-none transition-colors placeholder:text-subtle hover:border-subtle focus:border-primary focus:ring-2 focus:ring-primary/10"
            />
            {searchInput && (
              <button
                type="button"
                onClick={clearPolicySearch}
                aria-label="검색어 지우기"
                className="absolute right-[54px] top-0.5 flex h-11 w-10 items-center justify-center rounded-lg text-subtle outline-none transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-primary/20"
              >
                <X size={16} />
              </button>
            )}
            <button
              type="submit"
              className="absolute right-1 top-1 flex h-10 items-center justify-center rounded-lg bg-primary px-3 text-xs font-bold text-white outline-none transition-colors active:bg-primary-hover focus-visible:ring-2 focus-visible:ring-primary/25"
            >
              찾기
            </button>
          </div>
        </form>
      </section>

      <section className="mt-4 px-5">
        {tab === 'recommend' && (
          <>
            <div className="surface-panel p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-ink">
                  {recMeta
                    ? `${recMeta.total}개 후보 중 ${recMeta.filtered}개 정책`
                    : '맞춤 정책을 확인하고 있어요'}
                </p>
                <button
                  onClick={loadRecommendations}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface text-muted outline-none transition-colors hover:border-subtle hover:text-ink active:bg-line/40 focus-visible:ring-2 focus-visible:ring-primary/20"
                  aria-label="추천 새로고침"
                >
                  <RefreshCw size={16} className={recLoading ? 'animate-spin' : ''} />
                </button>
              </div>

              <p className="mt-2.5 text-xs font-semibold text-muted">추천 상태</p>
              <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                {RECOMMENDATION_FILTERS.map((filter) => {
                  const count = recMeta?.statusCounts[filter.key]
                  const active = recFilters.includes(filter.key)
                  return (
                    <CategoryChip
                      key={filter.key}
                      compact
                      active={active}
                      label={`${filter.label}${count === undefined ? '' : ` ${count}`}`}
                      onClick={() => {
                        const status = filter.key
                        setRecFilters((current) =>
                          current.includes(status)
                            ? current.filter((selected) => selected !== status)
                            : [...current, status],
                        )
                        setRecPage(0)
                      }}
                    />
                  )
                })}
              </div>
            </div>

            <div className="mt-3 space-y-3">
              {profileWarnings.map((warning) => (
                <Notice key={warning} tone="warning">
                  {warning}
                </Notice>
              ))}
              {recError && <ErrorBox message={recError} />}
              {!recError && recLoading && <InfoBox message="맞춤 정책을 계산하고 있어요." />}
              {!recLoading && !recError && recommendations.length > 0 && (
                <div className="surface-panel divide-y divide-line overflow-hidden">
                  {recommendations.map((policy) => (
                    <PolicyCard
                      key={policy.policy_id}
                      policy={policy}
                      saved={has(policy.policy_id)}
                      savePending={pendingSave === policy.policy_id}
                      onToggleSave={handleToggleSave}
                    />
                  ))}
                </div>
              )}
              {!recLoading && !recError && recommendations.length === 0 && (
                <InfoBox
                  message={
                    recFilters.length > 0
                      ? '선택한 분류에 해당하는 추천 정책이 없어요. 다른 분류를 선택해보세요.'
                      : '조건에 맞는 정책을 찾지 못했어요. 마이페이지에서 정보를 수정해보세요.'
                  }
                />
              )}
              {!recLoading && !recError && recMeta && recMeta.filtered > 0 && (
                <Pagination
                  page={recPage}
                  pageCount={recPageCount}
                  inputValue={recPageInput}
                  onInputChange={setRecPageInput}
                  onSubmit={goToRecommendationPage}
                  onPrevious={() => setRecPage((page) => page - 1)}
                  onNext={() => setRecPage((page) => page + 1)}
                  previousDisabled={recPage === 0}
                  nextDisabled={!recMeta.hasNext || recPage + 1 >= recPageCount}
                  label="추천 페이지"
                />
              )}
            </div>
          </>
        )}

        {tab === 'saved' && (
          <div className="space-y-3">
            <div className="surface-panel p-3">
              <p className="text-sm font-semibold text-ink">저장한 정책 {savedCards.length}개</p>
              <p className="mt-2.5 text-xs font-semibold text-muted">지원 분야</p>
              <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                <CategoryChip
                  compact
                  active={!savedCategory}
                  label="전체 분야"
                  onClick={() => setSavedCategory('')}
                />
                {NEED_OPTIONS.map((option) => (
                  <CategoryChip
                    key={option.tag}
                    compact
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
                    className="mt-1.5 h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm font-semibold text-ink outline-none transition-colors hover:border-subtle focus:border-primary focus:ring-2 focus:ring-primary/10"
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
                    className="mt-1.5 h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm font-semibold text-ink outline-none transition-colors hover:border-subtle focus:border-primary focus:ring-2 focus:ring-primary/10"
                  >
                    <option value="deadline">마감 임박순</option>
                    <option value="latest">최근 저장순</option>
                  </select>
                </label>
              </div>

              <label className="mt-2.5 flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-sm font-medium text-muted transition-colors hover:border-subtle">
                <input
                  type="checkbox"
                  checked={savedStatus === 'all'}
                  onChange={(event) => setSavedStatus(event.target.checked ? 'all' : 'available')}
                  className="h-4 w-4 accent-primary"
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
            {savedCards.length > 0 && (
              <div className="surface-panel divide-y divide-line overflow-hidden">
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
          </div>
        )}

        {tab === 'all' && (
          <div className="space-y-3">
            <div className="surface-panel p-3">
              <p className="text-sm font-semibold text-ink">
                {allQuery
                  ? allMeta
                    ? `검색 결과 ${allMeta.total}개`
                    : '검색 결과를 확인하고 있어요'
                  : allMeta
                    ? `${allMeta.total}개 정책`
                    : '전체 정책'}
              </p>
              {allQuery && (
                <p className="mt-1 line-clamp-1 text-xs font-medium text-muted">
                  검색어 ‘{allQuery}’
                </p>
              )}

              <p className="mt-2.5 text-xs font-semibold text-muted">지원 분야</p>
              <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                <CategoryChip
                  compact
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
                    compact
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
                    className="mt-1.5 h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm font-semibold text-ink outline-none transition-colors hover:border-subtle focus:border-primary focus:ring-2 focus:ring-primary/10"
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
                    className="mt-1.5 h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm font-semibold text-ink outline-none transition-colors hover:border-subtle focus:border-primary focus:ring-2 focus:ring-primary/10"
                  >
                    <option value="deadline">마감 임박순</option>
                    <option value="latest">최신 등록순</option>
                  </select>
                </label>
              </div>

              <label className="mt-2.5 flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-sm font-medium text-muted transition-colors hover:border-subtle">
                <input
                  type="checkbox"
                  checked={allStatus === 'all'}
                  onChange={(event) => {
                    setAllStatus(event.target.checked ? 'all' : 'available')
                    setAllPage(0)
                  }}
                  className="h-4 w-4 accent-primary"
                />
                마감된 정책도 보기
              </label>
            </div>

            {allLoading && <InfoBox message="전체 정책을 불러오는 중이에요." />}
            {allError && <ErrorBox message={allError} />}
            {!allLoading && !allError && all.length > 0 && (
              <div className="surface-panel divide-y divide-line overflow-hidden">
                {all.map((policy) => (
                  <PolicyCard
                    key={policy.policy_id}
                    policy={policy}
                    saved={has(policy.policy_id)}
                    savePending={pendingSave === policy.policy_id}
                    onToggleSave={handleToggleSave}
                  />
                ))}
              </div>
            )}
            {!allLoading && !allError && all.length === 0 && (
              <InfoBox
                message={
                  allQuery
                    ? '검색 결과가 없어요. 검색어를 줄이거나 다른 표현으로 찾아보세요.'
                    : '조건에 맞는 정책이 없어요. 다른 분야나 지역을 선택해보세요.'
                }
              />
            )}
            {!allLoading && !allError && allMeta && allMeta.total > 0 && (
              <Pagination
                page={allPage}
                pageCount={allPageCount}
                inputValue={allPageInput}
                onInputChange={setAllPageInput}
                onSubmit={goToAllPage}
                onPrevious={() => setAllPage((page) => page - 1)}
                onNext={() => setAllPage((page) => page + 1)}
                previousDisabled={allPage === 0}
                nextDisabled={!allMeta.has_next || allPage + 1 >= allPageCount}
                label="전체 정책 페이지"
              />
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
  return <Notice>{message}</Notice>
}

function CategoryChip({
  active,
  label,
  onClick,
  compact = false,
}: {
  active: boolean
  label: string
  onClick: () => void
  compact?: boolean
}) {
  return (
    <ChoiceChip
      selected={active}
      onClick={onClick}
      variant={compact ? 'compact' : 'pill'}
      className={compact ? 'w-full' : 'w-full px-2'}
    >
      {label}
    </ChoiceChip>
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
  return <Notice tone="error">{message}</Notice>
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
    <div className="surface-panel">
      <EmptyState
        icon={Search}
        title={title}
        description={description}
        actionLabel={actionLabel}
        onAction={onAction}
      />
    </div>
  )
}
