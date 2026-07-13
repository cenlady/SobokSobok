import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Sparkles } from 'lucide-react'
import TopBar from '../components/TopBar'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import { apiFetch, ApiError } from '../lib/api'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type { RecommendationPreviewResponse } from '../types'

type Tab = 'recommend' | 'saved' | 'all'

// 추천을 기본 진입 탭으로 둔다. 앱의 핵심 가치이고, '정책 찾기'를 눌렀을 때
// 수천 건의 전체 목록보다 맞춤 몇 건을 먼저 보는 게 자연스럽다.
const TABS: { key: Tab; label: string }[] = [
  { key: 'recommend', label: '✨ 추천' },
  { key: 'saved', label: '🔖 저장한' },
  { key: 'all', label: '📋 전체' },
]

/** 전체 정책 목록 API 응답 (별도 담당자 작업 — 아직 미배포일 수 있다) */
interface NormalizedPolicyListItem {
  id: string
  title: string
  summary?: string | null
  support_type?: string | null
  apply_end?: string | null
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
  const [allLoading, setAllLoading] = useState(false)
  const [allUnavailable, setAllUnavailable] = useState(false)

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
    try {
      const data = await apiFetch<NormalizedPolicyListItem[]>(
        '/api/v1/policies/normalized/?skip=0&limit=30',
      )
      setAll(
        data.map((p) => ({
          policy_id: p.id,
          title: p.title,
          summary: p.summary,
          support_type: p.support_type,
          apply_end: p.apply_end,
        })),
      )
      setAllUnavailable(false)
    } catch (error) {
      // 이 엔드포인트는 별도 담당자 작업이라 아직 없을 수 있다.
      // 404면 '준비 중'으로 안내하고, 나머지 탭은 정상 동작시킨다.
      setAllUnavailable(error instanceof ApiError && error.status === 404)
      setAll([])
    } finally {
      setAllLoading(false)
    }
  }, [])

  useEffect(() => {
    if (profileLoading) return
    if (tab === 'recommend' && recommendations.length === 0 && !recError) loadRecommendations()
    if (tab === 'all' && all.length === 0 && !allUnavailable) loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, profileLoading])

  const handleToggleSave = async (policyId: string) => {
    setPendingSave(policyId)
    try {
      await toggle(policyId)
    } finally {
      setPendingSave(null)
    }
  }

  const savedCards: PolicyCardData[] = saved.map((p) => ({
    policy_id: p.policy_id,
    title: p.title,
    summary: p.summary,
    support_type: p.support_type,
    apply_end: p.apply_end,
  }))

  return (
    <div className="pb-6">
      <TopBar />

      <section className="px-5">
        <h2 className="text-2xl font-bold text-brand-dark">정책 찾기</h2>

        {/* 세그먼트 탭 */}
        <div className="mt-4 flex gap-1 rounded-2xl bg-black/[0.04] p-1">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition-colors ${
                tab === key ? 'bg-white text-brand-dark shadow-card' : 'text-brand-dark/45'
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
              <p className="text-sm text-brand-dark/50">
                {recMeta
                  ? `${recMeta.total}개 후보 중 ${recMeta.returned}개를 골랐어요.`
                  : '내 정보 기준으로 정책을 찾는 중이에요.'}
              </p>
              <button
                onClick={loadRecommendations}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-brand-dark shadow-card active:scale-[0.97]"
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
          <div className="space-y-3">
            {savedLoading && <InfoBox message="저장한 정책을 불러오는 중이에요." />}
            {!savedLoading && savedCards.length === 0 && (
              <EmptyBox
                title="아직 저장한 정책이 없어요"
                description="추천 탭에서 마음에 드는 정책을 저장하면 홈 달력에 마감일이 표시돼요."
                actionLabel="추천 보러가기"
                onAction={() => setTab('recommend')}
              />
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
          <div className="space-y-3">
            {allLoading && <InfoBox message="전체 정책을 불러오는 중이에요." />}
            {allUnavailable && (
              <InfoBox message="전체 정책 조회는 준비 중이에요. 먼저 추천 탭을 이용해주세요." />
            )}
            {!allLoading &&
              all.map((policy) => (
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
    <div className="rounded-2xl bg-white p-4 text-sm font-medium text-brand-dark/60 shadow-card">
      {message}
    </div>
  )
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
      <h3 className="mt-4 text-lg font-bold text-brand-dark">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-brand-dark/60">{description}</p>
      <button
        onClick={onAction}
        className="mt-5 w-full rounded-2xl bg-brand-dark py-3 text-sm font-bold text-white active:scale-[0.99]"
      >
        {actionLabel}
      </button>
    </div>
  )
}
