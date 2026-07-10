import { useEffect, useState } from 'react'
import { ArrowRight, ChevronRight, CalendarDays, RefreshCw, Sparkles, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { benefits } from '../data/benefits'
import { ddayLabel } from '../lib/format'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile } from '../lib/storage'
import type { RecommendationPreviewResponse } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function HomeScreen() {
  const navigate = useNavigate()
  const { profile } = useProfile()
  const [recommendations, setRecommendations] = useState<RecommendationPreviewResponse | null>(null)
  const [loadingRecommendations, setLoadingRecommendations] = useState(false)
  const [recommendationError, setRecommendationError] = useState<string | null>(null)

  // 곧 마감되는 순으로 상위 노출
  const upcoming = [...benefits]
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate))
    .slice(0, 4)
  const count = upcoming.length

  const loadRecommendations = async () => {
    setLoadingRecommendations(true)
    setRecommendationError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/recommend/preview?limit=10`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildRecommendationRequest(profile)),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      setRecommendations((await response.json()) as RecommendationPreviewResponse)
    } catch {
      setRecommendationError('추천 API 연결을 확인해주세요.')
    } finally {
      setLoadingRecommendations(false)
    }
  }

  useEffect(() => {
    loadRecommendations()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  return (
    <div className="pb-6">
      <TopBar />

      {/* 인사 배너 */}
      <section className="px-5">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-accent-soft to-[#FBD9A8] p-6 shadow-card">
          <Sun
            className="absolute -right-6 -top-6 text-white/40"
            size={120}
            strokeWidth={1.2}
          />
          <span className="inline-flex items-center gap-1 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-brand-dark">
            ☀️ 좋은 아침입니다!
          </span>
          <h2 className="mt-3 text-2xl font-bold leading-snug text-brand-dark">
            {profile.ownerName} 사장님,
            <br />
            오늘 챙겨야 할 혜택이 <span className="text-brand">{count}건</span> 있어요!
          </h2>
          <p className="mt-2 text-sm text-brand-dark/70">
            놓치지 않도록 소복소복 메이가 도와드릴게요.
          </p>
          <button
            onClick={() => navigate('/chat')}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-dark/20 active:scale-[0.99]"
          >
            <Sparkles size={18} /> AI 추천 시작하기
          </button>
        </div>
      </section>

      {/* 실제 추천 정책 */}
      <section className="mt-7 px-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
              <Sparkles size={20} className="text-brand" /> 맞춤 추천 정책
            </h3>
            <p className="mt-1 text-sm text-brand-dark/50">
              {recommendations
                ? `${recommendations.total_candidates}개 후보 중 ${recommendations.returned}개를 골랐어요.`
                : '내 정보 기준으로 정책을 불러오는 중이에요.'}
            </p>
          </div>
          <button
            onClick={loadRecommendations}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-brand-dark shadow-card active:scale-[0.97]"
            aria-label="추천 새로고침"
          >
            <RefreshCw size={17} className={loadingRecommendations ? 'animate-spin' : ''} />
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {recommendationError && (
            <div className="rounded-2xl bg-white p-4 text-sm font-medium text-status-red shadow-card">
              {recommendationError}
            </div>
          )}

          {!recommendationError && loadingRecommendations && (
            <div className="rounded-2xl bg-white p-4 text-sm font-medium text-brand-dark/60 shadow-card">
              맞춤 정책을 계산하고 있어요.
            </div>
          )}

          {!loadingRecommendations &&
            recommendations?.results.slice(0, 5).map((item) => (
              <article key={item.policy_id} className="rounded-2xl bg-white p-4 shadow-card">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className={`rounded-lg px-2 py-0.5 text-xs font-bold ${
                          item.match_status === 'eligible'
                            ? 'bg-green-50 text-status-green'
                            : 'bg-blue-50 text-status-blue'
                        }`}
                      >
                        {item.match_status === 'eligible' ? '추천 가능' : '확인 필요'}
                      </span>
                      {item.support_type && (
                        <span className="rounded-lg bg-brand-light/20 px-2 py-0.5 text-xs font-semibold text-brand">
                          {item.support_type}
                        </span>
                      )}
                    </div>
                    <h4 className="mt-2 line-clamp-2 text-base font-bold leading-snug text-brand-dark">
                      {item.title}
                    </h4>
                  </div>
                  <span className="rounded-xl bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent">
                    {Math.round(item.rank_score)}점
                  </span>
                </div>
                {item.summary && (
                  <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-brand-dark/60">
                    {item.summary}
                  </p>
                )}
                <div className="mt-3 space-y-1">
                  {item.reasons.slice(0, 2).map((reason) => (
                    <p key={reason} className="text-xs font-medium text-brand-dark/60">
                      {reason}
                    </p>
                  ))}
                  {item.warnings[0] && (
                    <p className="text-xs font-medium text-status-blue">{item.warnings[0]}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    navigate(`/policy/${item.policy_id}`, {
                      state: { recommendation: item },
                    })
                  }
                  className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-dark py-2.5 text-sm font-semibold text-white active:scale-[0.99]"
                >
                  상세보기 <ArrowRight size={15} />
                </button>
              </article>
            ))}
        </div>
      </section>

      {/* 나의 혜택 달력 */}
      <section className="mt-7 px-5">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
            <CalendarDays size={20} className="text-brand" /> 나의 혜택 달력
          </h3>
          <button
            onClick={() => navigate('/calendar')}
            className="flex items-center text-sm font-medium text-brand-dark/50"
          >
            전체보기 <ChevronRight size={16} />
          </button>
        </div>
        <p className="mt-1 text-sm text-brand-dark/50">곧 마감되는 정보를 확인하세요.</p>

        <div className="no-scrollbar mt-4 flex gap-3 overflow-x-auto pb-1">
          {upcoming.map((b) => (
            <button
              key={b.id}
              onClick={() => navigate(`/benefit/${b.id}`)}
              className="w-44 flex-shrink-0 rounded-2xl bg-white p-4 text-left shadow-card active:scale-[0.98]"
            >
              <div className="flex items-center justify-between">
                <span
                  className={`rounded-lg px-2 py-0.5 text-xs font-bold ${
                    b.status === 'closing'
                      ? 'bg-red-50 text-status-red'
                      : b.status === 'open'
                        ? 'bg-green-50 text-status-green'
                        : 'bg-blue-50 text-status-blue'
                  }`}
                >
                  {ddayLabel(b.dueDate)}
                </span>
                <ArrowRight size={14} className="text-brand-dark/30" />
              </div>
              <p className="mt-3 line-clamp-2 text-[15px] font-semibold leading-snug text-brand-dark">
                {b.title}
              </p>
              {b.amount && (
                <p className="mt-2 text-xs font-medium text-brand-dark/60">
                  🎁 {b.amount}
                </p>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* 맞춤 정책 유도 카드 */}
      <section className="mt-7 px-5">
        <div className="rounded-3xl bg-white p-6 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft">
            <Sparkles size={22} className="text-accent" />
          </div>
          <h3 className="mt-4 text-lg font-bold leading-snug text-brand-dark">
            간단한 정보 입력으로
            <br />
            맞춤 정책을 찾아보세요!
          </h3>
          <p className="mt-2 text-sm text-brand-dark/60">
            AI가 사장님의 업종, 규모에 딱 맞는 지원금을 찾아드려요.
          </p>
          <button
            onClick={() => navigate('/onboarding')}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white active:scale-[0.99]"
          >
            내 정보 입력하기 <ArrowRight size={18} />
          </button>
        </div>
      </section>
    </div>
  )
}
