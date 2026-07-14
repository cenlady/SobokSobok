import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Bookmark,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  Download,
  FileText,
  LoaderCircle,
  MapPin,
  MessageCircleQuestion,
  Paperclip,
  Tag,
} from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import BottomNav from '../components/BottomNav'
import { API_BASE_URL, apiFetch } from '../lib/api'
import { formatDate } from '../lib/calendar'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type {
  PolicyDetailResponse,
  RecommendationExplanationResponse,
  RecommendationResult,
} from '../types'

export default function PolicyDetailScreen() {
  const { policyId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const recommendation = (location.state as { recommendation?: RecommendationResult } | null)
    ?.recommendation
  const { has, toggle } = useSavedPolicies()
  const { profile, loading: profileLoading } = useProfile()
  const [savePending, setSavePending] = useState(false)
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
    if (!policyId || !policy || profileLoading) return

    let ignore = false
    setExplaining(true)

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
            ? '등록한 사업장 정보와 주요 지원 조건이 잘 맞습니다.'
            : '신청 전에 세부 조건을 추가로 확인해야 합니다.'
        const fallbackStrengths = recommendation?.reasons?.length
          ? recommendation.reasons
          : ['업종과 사업장 정보를 기준으로 확인할 가치가 있는 정책입니다.']
        const fallbackAspects = recommendation?.warnings?.length
          ? recommendation.warnings
          : ['공고 원문에서 세부 자격 조건을 다시 확인해주세요.']

        const fallbackNext: string[] = []
        if (policy.apply_end) {
          const daysLeft = Math.ceil(
            (new Date(policy.apply_end).getTime() - Date.now()) / 86_400_000,
          )
          fallbackNext.push(
            daysLeft >= 0
              ? `마감일(${formatDate(policy.apply_end)})까지 ${daysLeft}일 남았습니다.`
              : '신청 기간이 마감되었는지 확인해주세요.',
          )
        } else {
          fallbackNext.push('신청 기한을 공고 원문에서 확인해주세요.')
        }
        fallbackNext.push('정책 문의에서 필요 서류와 접수 방법을 확인하세요.')

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

  if (loading) return <StateScreen label="정책 정보를 불러오는 중입니다." />
  if (error || !policy) return <StateScreen label={error || '정책 정보를 찾을 수 없습니다.'} />

  const regionText =
    policy.region_scope === 'national'
      ? '전국'
      : policy.matched_sidos.length > 0
        ? policy.matched_sidos.join(', ')
        : [policy.sido, policy.sigungu].filter(Boolean).join(' ') || '확인 필요'

  return (
    <div className="app-frame flex h-[100dvh] flex-col bg-cream">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-cream/95 px-4 backdrop-blur-sm">
        <button
          onClick={() => navigate(-1)}
          className="p-1 text-brand-dark active:opacity-60"
          aria-label="뒤로"
        >
          <ChevronLeft size={23} />
        </button>
        <h1 className="text-base font-semibold text-brand-dark">정책 상세</h1>
        <button
          onClick={toggleSave}
          disabled={savePending}
          className="p-1 disabled:opacity-40"
          aria-label={isSaved ? '정책 저장 해제' : '정책 저장'}
        >
          <Bookmark
            size={21}
            className={isSaved ? 'fill-brand text-brand' : 'text-brand-dark/35'}
          />
        </button>
      </header>

      <div className="no-scrollbar flex-1 overflow-y-auto px-5 pb-8 pt-5">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="font-semibold text-brand">{policy.support_type || '지원 정책'}</span>
          <span className="text-muted">{policy.status || '상태 확인 필요'}</span>
        </div>

        <h2 className="mt-3 text-[25px] font-bold leading-[1.35] tracking-[-0.03em] text-brand-dark">
          {policy.title}
        </h2>
        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          {policy.organization && <span>{policy.organization}</span>}
          {recommendation && (
            <>
              <span className="h-0.5 w-0.5 rounded-full bg-brand-dark/30" />
              <span>조건 일치도 {Math.round(recommendation.rank_score)}점</span>
            </>
          )}
        </div>

        {policy.summary && (
          <p className="mt-5 border-l-2 border-brand pl-4 text-[15px] leading-relaxed text-brand-dark/75">
            {policy.summary}
          </p>
        )}

        <div className="surface-panel mt-6 divide-y divide-line overflow-hidden">
          <InfoLine icon={MapPin} label="지원 지역" value={regionText} />
          <InfoLine
            icon={CalendarDays}
            label="신청 기간"
            value={`${formatDate(policy.apply_start)} ~ ${formatDate(policy.apply_end)}`}
          />
          <InfoLine icon={Tag} label="지원 유형" value={policy.support_type || '확인 필요'} />
        </div>

        <section className="mt-8 border-t border-line pt-7">
          <h3 className="section-title">내 정보와 맞는 조건</h3>
          <p className="mt-1 text-xs text-muted">등록한 사업장 정보와 공고 조건을 비교한 내용입니다.</p>

          {explaining && (
            <div className="mt-4 flex items-center gap-3 border-y border-line py-4 text-sm text-brand-dark/70">
              <LoaderCircle size={18} className="animate-spin text-brand" />
              사업장 정보와 공고 조건을 확인하고 있습니다.
            </div>
          )}

          {!explaining && explanation && (
            <div className="mt-4 space-y-5">
              <p className="border-l-2 border-brand-light pl-3 text-sm font-medium leading-relaxed text-brand-dark">
                {explanation.summary}
              </p>

              {explanation.strengths.length > 0 && (
                <ExplanationList
                  title="조건이 맞는 부분"
                  icon={CheckCircle2}
                  tone="good"
                  items={explanation.strengths}
                />
              )}

              {explanation.aspects_to_check.length > 0 && (
                <ExplanationList
                  title="신청 전 확인할 부분"
                  icon={AlertCircle}
                  tone="check"
                  items={explanation.aspects_to_check}
                />
              )}

              {explanation.next_actions.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-brand-dark">다음에 할 일</h4>
                  <ol className="mt-2 border-y border-line">
                    {explanation.next_actions.map((action, index) => (
                      <li
                        key={action}
                        className="flex gap-3 border-b border-line py-3 text-sm leading-relaxed text-brand-dark/75 last:border-b-0"
                      >
                        <span className="w-5 flex-shrink-0 font-semibold tabular-nums text-brand">
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <span>{action.replace(/^-\s*/, '')}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </section>

        <Section title="지원 대상" content={policy.target_text} />
        <Section title="지원 내용" content={policy.support_content || policy.body} />
        <Section title="필요 서류" content={documentList(policy.required_documents)} />

        {policy.attachments && policy.attachments.length > 0 && (
          <section className="mt-8 border-t border-line pt-7">
            <h3 className="section-title flex items-center gap-2">
              <Paperclip size={17} className="text-brand" /> 첨부 파일
            </h3>
            <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
              {policy.attachments.map((file) => (
                <a
                  key={file.attachment_file_id}
                  href={`${API_BASE_URL}/api/v1/policies/attachments/${file.attachment_file_id}/download`}
                  download={file.original_file_name || 'attachment'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-4 py-3.5 active:bg-black/[0.02]"
                >
                  <FileText size={17} className="flex-shrink-0 text-brand" />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-brand-dark/80">
                    {file.original_file_name || '첨부파일'}
                  </span>
                  <Download size={15} className="flex-shrink-0 text-muted" />
                </a>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="space-y-2 border-t border-line bg-surface px-5 py-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate(`/chat?policyId=${policy.id}`)}
            className="secondary-button flex items-center justify-center gap-1.5 px-2"
          >
            <MessageCircleQuestion size={16} /> 정책에 대해 물어보기
          </button>
          <AddToCalendarButton policyId={policy.id} applyEnd={policy.apply_end} variant="full" />
        </div>
        <button
          disabled={!policy.apply_url}
          onClick={() =>
            policy.apply_url && window.open(policy.apply_url, '_blank', 'noopener,noreferrer')
          }
          className="primary-button flex w-full items-center justify-center gap-2 py-3.5 text-base"
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
      <p className="text-sm text-muted">{label}</p>
      <button onClick={() => navigate('/')} className="primary-button">
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
    <div className="flex items-start gap-3 px-4 py-3.5">
      <Icon size={17} className="mt-0.5 flex-shrink-0 text-brand" />
      <span className="w-16 flex-shrink-0 text-sm text-muted">{label}</span>
      <span className="min-w-0 text-sm font-medium leading-relaxed text-brand-dark">{value}</span>
    </div>
  )
}

function ExplanationList({
  title,
  icon: Icon,
  tone,
  items,
}: {
  title: string
  icon: typeof CheckCircle2
  tone: 'good' | 'check'
  items: string[]
}) {
  return (
    <div>
      <h4 className="flex items-center gap-2 text-sm font-semibold text-brand-dark">
        <Icon size={16} className={tone === 'good' ? 'text-status-green' : 'text-status-blue'} />
        {title}
      </h4>
      <ul className="mt-2 border-y border-line">
        {items.map((item) => (
          <li
            key={item}
            className="flex gap-2.5 border-b border-line py-3 text-sm leading-relaxed text-brand-dark/75 last:border-b-0"
          >
            <span
              className={`mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full ${
                tone === 'good' ? 'bg-status-green' : 'bg-status-blue'
              }`}
            />
            <span>{item.replace(/^-\s*/, '')}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Section({ title, content }: { title: string; content?: string | null }) {
  if (!content) return null
  return (
    <section className="mt-8 border-t border-line pt-7">
      <h3 className="section-title">{title}</h3>
      <p className="mt-3 whitespace-pre-line text-[15px] leading-[1.75] text-brand-dark/75">
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
