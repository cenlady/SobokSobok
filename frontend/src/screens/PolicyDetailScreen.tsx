import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  Bot,
  Bookmark,
  CalendarDays,
  ChevronLeft,
  MapPin,
  Sparkles,
  Tag,
  CheckCircle2,
  AlertCircle,
  Zap,
  Paperclip,
  FileText,
  Download,
} from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import BottomNav from '../components/BottomNav'
import { buildGoogleCalendarUrl, formatDate } from '../lib/calendar'
import { useSavedPolicies, useProfile } from '../lib/storage'
import { buildRecommendationRequest } from '../lib/recommend'
import type {
  PolicyDetailResponse,
  RecommendationResult,
  SavedPolicy,
  RecommendationExplanationResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function PolicyDetailScreen() {
  const { policyId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const recommendation = (location.state as { recommendation?: RecommendationResult } | null)
    ?.recommendation
  const { has, get, save, remove } = useSavedPolicies()
  const { profile } = useProfile()
  const [policy, setPolicy] = useState<PolicyDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<RecommendationExplanationResponse | null>(null)
  const [explaining, setExplaining] = useState(false)

  useEffect(() => {
    if (!policyId) return
    let ignore = false
    setLoading(true)
    setError(null)

    fetch(`${API_BASE_URL}/api/v1/policies/normalized/${policyId}`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<PolicyDetailResponse>
      })
      .then((data) => {
        if (!ignore) setPolicy(data)
      })
      .catch(() => {
        if (!ignore) setError('정책 상세 정보를 불러오지 못했어요.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [policyId])

  useEffect(() => {
    if (!policyId || !policy) return
    let ignore = false
    setExplaining(true)

    fetch(`${API_BASE_URL}/api/v1/recommend/explain/${policyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(buildRecommendationRequest(profile)),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<RecommendationExplanationResponse>
      })
      .then((data) => {
        if (!ignore) setExplanation(data)
      })
      .catch((err) => {
        console.error('Explanation fetch failed, fallback to local:', err)
        if (ignore) return
        
        const fallbackSummary = recommendation?.match_status === 'eligible'
          ? '지원 조건 충족률이 높은 추천 정책입니다.'
          : recommendation?.match_status === 'near_match'
            ? '일부 선호 조건이 달라 참고용으로 제공한 유사 정책입니다.'
            : '세부 조건 확인이 필요한 추천 정책입니다.'
        const fallbackStrengths = recommendation?.reasons && recommendation.reasons.length > 0
          ? recommendation.reasons
          : ['사용자 업종 및 사업자 정보에 부합하는 지원 정책입니다.']
        const fallbackAspects = recommendation?.warnings && recommendation.warnings.length > 0
          ? recommendation.warnings
          : ['상세 공고의 세부 자격 조건을 다시 한번 확인해 보세요.']
        
        const fallbackNext = []
        if (policy.apply_end) {
          const daysLeft = Math.ceil((new Date(policy.apply_end).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))
          if (daysLeft >= 0) {
            fallbackNext.push(`마감일(${formatDate(policy.apply_end)})까지 ${daysLeft}일 남았으니 늦지 않게 신청해 보세요.`)
          } else {
            fallbackNext.push('신청 기간이 마감되었는지 확인해 보세요.')
          }
        } else {
          fallbackNext.push('신청 기한을 확인해 보세요.')
        }
        fallbackNext.push("우측 하단의 'AI 상담' 버튼을 눌러 상세 지원 서류와 자격을 물어보세요.")

        setExplanation({
          summary: fallbackSummary,
          strengths: fallbackStrengths,
          aspects_to_check: fallbackAspects,
          next_actions: fallbackNext
        })
      })
      .finally(() => {
        if (!ignore) setExplaining(false)
      })

    return () => {
      ignore = true
    }
  }, [policyId, policy, profile, recommendation])

  const savedPolicy = useMemo(() => {
    if (!policy) return null
    const current = get(policy.id)
    return toSavedPolicy(policy, recommendation, current?.saved_at)
  }, [get, policy, recommendation])

  const isSaved = policy ? has(policy.id) : false

  const toggleSave = () => {
    if (!policy || !savedPolicy) return
    if (isSaved) {
      remove(policy.id)
    } else {
      save(savedPolicy)
    }
  }

  const openGoogleCalendar = () => {
    if (!savedPolicy) return
    window.open(buildGoogleCalendarUrl(savedPolicy), '_blank', 'noopener,noreferrer')
  }

  if (loading) {
    return <StateScreen label="정책 정보를 불러오는 중이에요." />
  }

  if (error || !policy) {
    return <StateScreen label={error || '정책 정보를 찾을 수 없어요.'} />
  }

  const regionText =
    policy.region_scope === 'national'
      ? '전국'
      : policy.matched_sidos.length > 0
        ? policy.matched_sidos.join(', ')
        : [policy.sido, policy.sigungu].filter(Boolean).join(' ') || '확인 필요'
  return (
    <div className="app-frame flex h-[100dvh] flex-col bg-cream">
      <header className="sticky top-0 z-10 flex items-center justify-between bg-cream/95 px-4 py-4 backdrop-blur">
        <button onClick={() => navigate(-1)} className="p-1 text-brand-dark active:opacity-60">
          <ChevronLeft size={26} />
        </button>
        <h1 className="text-lg font-semibold text-brand-dark">정책 상세</h1>
        <button onClick={toggleSave} className="p-1" aria-label="정책 저장">
          <Bookmark
            size={24}
            className={isSaved ? 'fill-brand text-brand' : 'text-brand-dark/40'}
          />
        </button>
      </header>

      <div className="no-scrollbar flex-1 overflow-y-auto px-5 pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-lg bg-brand-light/20 px-2.5 py-1 text-sm font-bold text-brand">
            {policy.support_type || '지원정책'}
          </span>
          {recommendation && (
            <span className="rounded-lg bg-accent-soft px-2.5 py-1 text-sm font-bold text-accent">
              {Math.round(recommendation.rank_score)}점
            </span>
          )}
          <span className="rounded-lg bg-white px-2.5 py-1 text-sm font-semibold text-brand-dark/60">
            {policy.status || '상태 확인'}
          </span>
        </div>

        <h2 className="mt-4 text-2xl font-bold leading-snug text-brand-dark">
          {policy.title}
        </h2>
        {policy.organization && (
          <p className="mt-2 text-sm font-semibold text-brand-dark/50">{policy.organization}</p>
        )}
        {policy.summary && (
          <p className="mt-4 rounded-2xl bg-white p-4 text-[15px] leading-relaxed text-brand-dark/70 shadow-card">
            {policy.summary}
          </p>
        )}

        <div className="mt-5 space-y-3 rounded-2xl bg-white p-5 shadow-card">
          <InfoLine icon={MapPin} label="지역" value={regionText} />
          <InfoLine
            icon={CalendarDays}
            label="기간"
            value={`${formatDate(policy.apply_start)} ~ ${formatDate(policy.apply_end)}`}
          />
          <InfoLine icon={Tag} label="유형" value={policy.support_type || '확인 필요'} />
        </div>

        {/* AI 추천 이유 및 설명 로딩 상태 */}
        {explaining && (
          <section className="mt-6">
            <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
              <Sparkles size={19} className="text-brand animate-pulse" /> AI 추천 이유
            </h3>
            <div className="mt-3 rounded-2xl bg-white p-5 shadow-card border border-brand/5 flex flex-col items-center justify-center text-center gap-3 py-7 animate-pulse">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-brand-light/10 text-brand">
                <Sparkles size={20} className="animate-bounce" />
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/10 opacity-75"></span>
              </div>
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-brand-dark">AI가 추천 이유를 분석 중이에요</p>
                <p className="text-[12px] font-medium text-brand-dark/50">소복이가 사장님의 조건과 공고 내용을 대조해보고 있어요.</p>
              </div>
            </div>
          </section>
        )}

        {!explaining && explanation && (
          <div className="space-y-6">
            {/* AI 추천 이유 (한 줄 요약) */}
            <section className="mt-6">
              <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
                <Sparkles size={19} className="text-brand fill-brand/10" /> AI 추천 이유
              </h3>
              <div className="mt-3 rounded-2xl bg-white p-4 shadow-card border-l-4 border-brand">
                <p className="text-[15px] font-bold leading-relaxed text-brand-dark">
                  {explanation.summary}
                </p>
              </div>
            </section>

            {/* 잘 맞는 부분 */}
            {explanation.strengths.length > 0 && (
              <section className="mt-6">
                <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
                  <CheckCircle2 size={19} className="text-brand" /> 잘 맞는 부분
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.strengths.map((strength) => (
                    <div key={strength} className="flex items-start gap-2 rounded-2xl bg-white p-3.5 shadow-card">
                      <span className="text-brand font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-brand-dark/80">
                        {strength.replace(/^-\s*/, '')}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 확인할 부분 */}
            {explanation.aspects_to_check.length > 0 && (
              <section className="mt-6">
                <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
                  <AlertCircle size={19} className="text-status-blue" /> 확인할 부분
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.aspects_to_check.map((warning) => (
                    <div key={warning} className="flex items-start gap-2 rounded-2xl bg-blue-50/60 p-3.5 shadow-card">
                      <span className="text-status-blue font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-status-blue">
                        {warning.replace(/^-\s*/, '')}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 다음 행동 */}
            {explanation.next_actions.length > 0 && (
              <section className="mt-6">
                <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
                  <Zap size={19} className="text-accent" /> 다음 행동
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.next_actions.map((action) => (
                    <div key={action} className="flex items-start gap-2 rounded-2xl bg-accent-soft/45 p-3.5 shadow-card">
                      <span className="text-accent font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-brand-dark">
                        {action.replace(/^-\s*/, '')}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        <Section title="지원 대상" content={policy.target_text} />
        <Section title="지원 내용" content={policy.support_content || policy.body} />
        <Section title="필요 서류" content={documentList(policy.required_documents)} />

        {policy.attachments && policy.attachments.length > 0 && (
          <section className="mt-6">
            <h3 className="text-lg font-bold text-brand-dark flex items-center gap-1.5">
              <Paperclip size={18} className="text-brand" /> 첨부 파일
            </h3>
            <div className="mt-3 space-y-2">
              {policy.attachments.map((file) => (
                <a
                  key={file.attachment_file_id}
                  href={`${API_BASE_URL}/api/v1/policies/attachments/${file.attachment_file_id}/download`}
                  download={file.original_file_name || 'attachment'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-2xl bg-white p-3.5 shadow-card hover:bg-black/[0.01] active:scale-[0.99] transition-transform duration-100"
                >
                  <FileText size={18} className="text-brand flex-shrink-0" />
                  <span className="text-[14px] font-semibold truncate flex-1 text-brand-dark/80">
                    {file.original_file_name || '첨부파일'}
                  </span>
                  <Download size={16} className="text-brand-dark/30 flex-shrink-0" />
                </a>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="space-y-2 border-t border-black/5 bg-cream px-5 py-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate(`/chat?policyId=${policy.id}`)}
            className="flex items-center justify-center gap-1.5 rounded-2xl bg-white py-3 text-sm font-bold text-brand-dark shadow-card active:scale-[0.99]"
          >
            <Bot size={17} /> AI 상담
          </button>
          <button
            onClick={openGoogleCalendar}
            className="flex items-center justify-center gap-1.5 rounded-2xl bg-white py-3 text-sm font-bold text-brand-dark shadow-card active:scale-[0.99]"
          >
            <CalendarDays size={17} /> 구글 캘린더
          </button>
        </div>
        <button
          disabled={!policy.apply_url}
          onClick={() => policy.apply_url && window.open(policy.apply_url, '_blank', 'noopener,noreferrer')}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-accent py-3.5 text-base font-bold text-white disabled:bg-brand-dark/20 active:scale-[0.99]"
        >
          신청 페이지 보기 <ArrowRight size={17} />
        </button>
      </div>
      <BottomNav />
    </div>
  )
}

function toSavedPolicy(
  policy: PolicyDetailResponse,
  recommendation?: RecommendationResult,
  savedAt?: string,
): SavedPolicy {
  return {
    policy_id: policy.id,
    title: policy.title,
    summary: policy.summary,
    organization: policy.organization,
    support_type: policy.support_type,
    apply_start: policy.apply_start,
    apply_end: policy.apply_end,
    apply_url: policy.apply_url,
    rank_score: recommendation?.rank_score,
    match_status: recommendation?.match_status,
    reasons: recommendation?.reasons,
    warnings: recommendation?.warnings,
    saved_at: savedAt || new Date().toISOString(),
  }
}

function StateScreen({ label }: { label: string }) {
  const navigate = useNavigate()
  return (
    <div className="app-frame flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-cream px-6 text-center">
      <p className="text-brand-dark/60">{label}</p>
      <button onClick={() => navigate('/')} className="rounded-xl bg-brand-dark px-5 py-2.5 text-white">
        홈으로
      </button>
    </div>
  )
}

function InfoLine({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Tag
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon size={18} className="mt-0.5 flex-shrink-0 text-brand" />
      <span className="w-12 flex-shrink-0 text-sm text-brand-dark/50">{label}</span>
      <span className="min-w-0 text-[15px] font-semibold text-brand-dark">{value}</span>
    </div>
  )
}

function Section({ title, content }: { title: string; content?: string | null }) {
  if (!content) return null
  return (
    <section className="mt-6">
      <h3 className="text-lg font-bold text-brand-dark">{title}</h3>
      <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed text-brand-dark/70">
        {content}
      </p>
    </section>
  )
}

function documentList(documents: unknown[]) {
  if (documents.length === 0) return null
  return documents
    .map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'name' in item) {
        return String((item as { name?: unknown }).name || '')
      }
      return ''
    })
    .filter(Boolean)
    .join('\n')
}
