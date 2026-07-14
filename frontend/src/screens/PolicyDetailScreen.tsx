import { useEffect, useState } from 'react'
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
import AddToCalendarButton from '../components/AddToCalendarButton'
import BottomNav from '../components/BottomNav'
import { API_BASE_URL, apiFetch } from '../lib/api'
import { formatDate } from '../lib/calendar'
import { formatPeriod, getDeadlineInfo } from '../lib/deadline'
import { StatusBadge } from '../components/ui'
import { useSavedPolicies, useProfile } from '../lib/storage'
import { buildRecommendationRequest } from '../lib/recommend'
import type {
  PolicyDetailResponse,
  RecommendationResult,
  RecommendationExplanationResponse,
} from '../types'

export default function PolicyDetailScreen() {
  const { policyId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  // 추천 탭에서 넘어온 경우에만 채워진다. 없어도 서버가 설명을 만들어주므로 필수는 아니다.
  const recommendation = (location.state as { recommendation?: RecommendationResult } | null)
    ?.recommendation
  const { has, toggle } = useSavedPolicies()
  const [savePending, setSavePending] = useState(false)
  const { profile, loading: profileLoading } = useProfile()
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

    apiFetch<PolicyDetailResponse>(`/api/v1/policies/normalized/${policyId}`)
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
    // 프로필은 서버에서 비동기로 온다. 빈 프로필로 요청하면 엉뚱한 설명이 나온다.
    if (profileLoading) return

    let ignore = false
    setExplaining(true)

    // apiFetch를 써야 JWT가 붙는다. /recommend는 인증 가드가 걸려 있어
    // 날것의 fetch로는 401이 나고 설명이 통째로 사라진다.
    apiFetch<RecommendationExplanationResponse>(`/api/v1/recommend/explain/${policyId}`, {
      method: 'POST',
      json: buildRecommendationRequest(profile),
    })
      .then((data) => {
        if (!ignore) setExplanation(data)
      })
      .catch((err) => {
        console.error('추천 설명 생성 실패, 로컬 폴백 사용:', err)
        if (ignore) return

        const fallbackSummary =
          recommendation?.match_status === 'eligible'
            ? '지원 조건 충족률이 높은 추천 정책입니다.'
            : '세부 조건 확인이 필요한 정책입니다.'
        const fallbackStrengths = recommendation?.reasons?.length
          ? recommendation.reasons
          : ['사용자 업종 및 사업자 정보에 부합하는 지원 정책입니다.']
        const fallbackAspects = recommendation?.warnings?.length
          ? recommendation.warnings
          : ['상세 공고의 세부 자격 조건을 다시 한번 확인해 보세요.']

        const fallbackNext: string[] = []
        if (policy.apply_end) {
          const daysLeft = Math.ceil(
            (new Date(policy.apply_end).getTime() - Date.now()) / 86_400_000,
          )
          fallbackNext.push(
            daysLeft >= 0
              ? `마감일(${formatDate(policy.apply_end)})까지 ${daysLeft}일 남았으니 늦지 않게 신청해 보세요.`
              : '신청 기간이 마감되었는지 확인해 보세요.',
          )
        } else {
          fallbackNext.push('신청 기한을 확인해 보세요.')
        }
        fallbackNext.push('챗봇 탭에서 상세 지원 서류와 자격을 물어보세요.')

        setExplanation({
          summary: fallbackSummary,
          strengths: fallbackStrengths,
          aspects_to_check: fallbackAspects,
          next_actions: fallbackNext,
        })
      })
      .finally(() => {
        if (!ignore) setExplaining(false)
      })

    return () => {
      ignore = true
    }
  }, [policyId, policy, profile, profileLoading, recommendation])

  const isSaved = policy ? has(policy.id) : false

  const toggleSave = async () => {
    if (!policy || savePending) return
    setSavePending(true)
    try {
      await toggle(policy.id)
    } finally {
      setSavePending(false)
    }
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
        <button onClick={() => navigate(-1)} className="p-1 text-ink active:opacity-60">
          <ChevronLeft size={26} />
        </button>
        <h1 className="text-lg font-semibold text-ink">정책 상세</h1>
        <button onClick={toggleSave} className="p-1" aria-label="정책 저장">
          <Bookmark
            size={24}
            className={isSaved ? 'fill-brand text-brand' : 'text-subtle'}
          />
        </button>
      </header>

      <div className="no-scrollbar flex-1 overflow-y-auto px-5 pb-6">
        {/* 상태 배지는 하나. 예전에는 유형·점수·status 원시값(open/notice)이 나란히
            붙어 있었고, 특히 status는 DB 값이 그대로 화면에 노출되고 있었다. */}
        <StatusBadge info={getDeadlineInfo(policy)} />

        <h2 className="mt-3 text-title leading-snug text-ink">{policy.title}</h2>
        {policy.organization && (
          <p className="mt-2 text-sm font-semibold text-muted">{policy.organization}</p>
        )}
        {policy.summary && (
          <p className="mt-4 rounded-2xl bg-white p-4 text-[15px] leading-relaxed text-muted shadow-card">
            {policy.summary}
          </p>
        )}

        <div className="mt-5 space-y-3 rounded-2xl bg-white p-5 shadow-card">
          <InfoLine icon={MapPin} label="지역" value={regionText} />
          {/* 날짜가 없으면 "미정 ~ 미정" 대신, 상시 접수인지 우리가 모르는지를 말한다.
              둘은 전혀 다른 얘기다. */}
          <InfoLine
            icon={CalendarDays}
            label="기간"
            value={formatPeriod(policy) ?? getDeadlineInfo(policy).label}
          />
          {policy.support_type && (
            <InfoLine icon={Tag} label="유형" value={policy.support_type} />
          )}
        </div>

        {/* AI 추천 이유 및 설명 로딩 상태 */}
        {explaining && (
          <section className="mt-6">
            <h3 className="flex items-center gap-1.5 text-section text-ink">
              <Sparkles size={19} className="text-brand animate-pulse" /> AI 추천 이유
            </h3>
            <div className="mt-3 rounded-2xl bg-white p-5 shadow-card border border-brand/5 flex flex-col items-center justify-center text-center gap-3 py-7 animate-pulse">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-brand-light/10 text-brand">
                <Sparkles size={20} className="animate-bounce" />
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/10 opacity-75"></span>
              </div>
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-ink">AI가 추천 이유를 분석 중이에요</p>
                <p className="text-[12px] font-medium text-muted">소복이가 사장님의 조건과 공고 내용을 대조해보고 있어요.</p>
              </div>
            </div>
          </section>
        )}

        {!explaining && explanation && (
          <div className="space-y-6">
            {/* AI 추천 이유 (한 줄 요약) */}
            <section className="mt-6">
              <h3 className="flex items-center gap-1.5 text-section text-ink">
                <Sparkles size={19} className="text-brand fill-brand/10" /> AI 추천 이유
              </h3>
              <div className="mt-3 rounded-2xl bg-white p-4 shadow-card border-l-4 border-brand">
                <p className="text-[15px] font-bold leading-relaxed text-ink">
                  {explanation.summary}
                </p>
              </div>
            </section>

            {/* 잘 맞는 부분 */}
            {explanation.strengths.length > 0 && (
              <section className="mt-6">
                <h3 className="flex items-center gap-1.5 text-section text-ink">
                  <CheckCircle2 size={19} className="text-brand" /> 잘 맞는 부분
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.strengths.map((strength) => (
                    <div key={strength} className="flex items-start gap-2 rounded-2xl bg-white p-3.5 shadow-card">
                      <span className="text-brand font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-ink">
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
                <h3 className="flex items-center gap-1.5 text-section text-ink">
                  <AlertCircle size={19} className="text-muted" /> 확인할 부분
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.aspects_to_check.map((warning) => (
                    <div key={warning} className="flex items-start gap-2 rounded-2xl bg-blue-50/60 p-3.5 shadow-card">
                      <span className="text-muted font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-muted">
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
                <h3 className="flex items-center gap-1.5 text-section text-ink">
                  <Zap size={19} className="text-accent" /> 다음 행동
                </h3>
                <div className="mt-3 space-y-2">
                  {explanation.next_actions.map((action) => (
                    <div key={action} className="flex items-start gap-2 rounded-2xl bg-accent-soft/45 p-3.5 shadow-card">
                      <span className="text-accent font-bold mt-0.5">•</span>
                      <p className="text-sm font-semibold text-ink">
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
            <h3 className="text-section text-ink flex items-center gap-1.5">
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
                  <span className="text-[14px] font-semibold truncate flex-1 text-ink">
                    {file.original_file_name || '첨부파일'}
                  </span>
                  <Download size={16} className="text-subtle flex-shrink-0" />
                </a>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="space-y-2 border-t border-line bg-cream px-5 py-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate(`/chat?policyId=${policy.id}`)}
            className="flex items-center justify-center gap-1.5 rounded-2xl bg-white py-3 text-sm font-bold text-ink shadow-card active:scale-[0.99]"
          >
            <Bot size={17} /> AI 상담
          </button>
          <AddToCalendarButton policyId={policy.id} applyEnd={policy.apply_end} variant="full" />
        </div>
        <button
          disabled={!policy.apply_url}
          onClick={() => policy.apply_url && window.open(policy.apply_url, '_blank', 'noopener,noreferrer')}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-accent py-3.5 text-base font-bold text-white disabled:bg-subtle active:scale-[0.99]"
        >
          신청 페이지 보기 <ArrowRight size={17} />
        </button>
      </div>
      <BottomNav />
    </div>
  )
}

function StateScreen({ label }: { label: string }) {
  const navigate = useNavigate()
  return (
    <div className="app-frame flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-cream px-6 text-center">
      <p className="text-muted">{label}</p>
      <button onClick={() => navigate('/')} className="rounded-xl bg-primary px-5 py-2.5 text-white">
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
      <span className="w-12 flex-shrink-0 text-sm text-muted">{label}</span>
      <span className="min-w-0 text-[15px] font-semibold text-ink">{value}</span>
    </div>
  )
}

function Section({ title, content }: { title: string; content?: string | null }) {
  if (!content) return null
  return (
    <section className="mt-6">
      <h3 className="text-section text-ink">{title}</h3>
      <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed text-muted">
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
