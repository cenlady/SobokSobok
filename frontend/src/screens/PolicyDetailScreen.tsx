import { useEffect, useState } from 'react'
import {
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  MessageCircle,
  CalendarDays,
  ChevronDown,
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
  ShieldCheck,
} from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import BottomNav from '../components/BottomNav'
import { API_BASE_URL, apiFetch } from '../lib/api'
import { formatDate } from '../lib/calendar'
import { formatPeriod, getDeadlineInfo } from '../lib/deadline'
import { cleanPolicyText, truncateAtSentence } from '../lib/text'
import { IconButton, StatusBadge } from '../components/ui'
import { useSavedPolicies, useProfile } from '../lib/storage'
import { buildRecommendationRequest } from '../lib/recommend'
import type {
  PolicyDetailResponse,
  RecommendationResult,
  RecommendationExplanationResponse,
} from '../types'

const explanationRequests = new Map<string, Promise<RecommendationExplanationResponse>>()

function requestExplanation(policyId: string, requestBody: unknown) {
  const cacheKey = `${policyId}:${JSON.stringify(requestBody)}`
  const cached = explanationRequests.get(cacheKey)
  if (cached) return cached

  const request = apiFetch<RecommendationExplanationResponse>(
    `/api/v1/recommend/explain/${policyId}`,
    { method: 'POST', json: requestBody },
  ).catch((error) => {
    explanationRequests.delete(cacheKey)
    throw error
  })
  if (explanationRequests.size >= 50) {
    const oldestKey = explanationRequests.keys().next().value
    if (oldestKey) explanationRequests.delete(oldestKey)
  }
  explanationRequests.set(cacheKey, request)
  return request
}

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
    requestExplanation(policyId, buildRecommendationRequest(profile))
      .then((data) => {
        if (!ignore) setExplanation(data)
      })
      .catch((err) => {
        console.error('추천 설명 생성 실패, 로컬 폴백 사용:', err)
        if (ignore) return

        const fallbackEligibility = recommendation?.eligibility_status || 'needs_review'
        const fallbackPreference = recommendation?.preference_match || 'not_requested'
        const fallbackSummary =
          fallbackEligibility === 'eligible' && fallbackPreference === 'none'
            ? '자격 조건은 맞지만 선택한 관심 분야와 직접 일치하지 않습니다.'
            : fallbackEligibility === 'eligible'
              ? '입력한 조건과 확인된 공고 조건이 잘 맞습니다.'
              : '맞는 조건은 있지만 세부 자격 확인이 필요합니다.'
        const fallbackStrengths = recommendation?.reasons?.length
          ? recommendation.reasons
          : []
        const fallbackAspects = [
          ...(recommendation?.unmet_conditions || []),
          ...(recommendation?.warnings || []),
        ]

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
          match_status: recommendation?.match_status || 'needs_review',
          eligibility_status: fallbackEligibility,
          preference_match: fallbackPreference,
          confidence: recommendation?.confidence || 'low',
          generated_by: 'rules',
          summary: fallbackSummary,
          strengths: fallbackStrengths,
          aspects_to_check:
            fallbackAspects.length > 0
              ? fallbackAspects
              : ['상세 공고의 세부 자격 조건을 다시 한번 확인해 보세요.'],
          next_actions: fallbackNext,
          evidence: policy.target_text
            ? [`지원 대상 원문: ${policy.target_text.slice(0, 240)}`]
            : [],
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
  const applicationMethodText = formatApplicationMethods(policy.application_methods)
  const contactText = formatContactPoints(policy.contact_points)
  const eligibilityText = formatEligibility(policy.eligibility)

  return (
    <div className="app-frame flex h-[100dvh] flex-col bg-cream">
      <header className="sticky top-0 z-10 flex items-center justify-between bg-cream/95 px-3 py-2 backdrop-blur">
        <IconButton icon={ChevronLeft} onClick={() => navigate(-1)} label="뒤로" />
        <h1 className="text-[15px] font-semibold text-ink">정책 상세</h1>
        <IconButton
          icon={isSaved ? BookmarkCheck : Bookmark}
          onClick={toggleSave}
          disabled={savePending}
          active={isSaved}
          label={isSaved ? '저장 해제' : '정책 저장'}
        />
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
          <p className="mt-4 rounded-2xl bg-surface p-4 text-[15px] leading-relaxed text-muted shadow-card">
            {policy.summary}
          </p>
        )}

        <div className="mt-5 space-y-3 rounded-2xl bg-surface p-5 shadow-card">
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

        {/* 맞춤 추천 이유 및 설명 로딩 상태 */}
        {explaining && (
          <section className="mt-6">
            <h3 className="flex items-center gap-1.5 text-section text-ink">
              <Sparkles size={19} className="text-brand animate-pulse" /> 맞춤 추천 이유
            </h3>
            <div className="mt-3 rounded-2xl bg-surface p-5 shadow-card border border-brand/5 flex flex-col items-center justify-center text-center gap-3 py-7 animate-pulse">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-full bg-brand-light/10 text-brand">
                <Sparkles size={20} className="animate-bounce" />
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/10 opacity-75"></span>
              </div>
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-ink">추천 근거를 확인하고 있어요</p>
                <p className="text-[12px] font-medium text-muted">입력 정보와 공고 조건을 항목별로 대조하고 있어요.</p>
              </div>
            </div>
          </section>
        )}

        {!explaining && explanation && (
          <div className="space-y-6">
            {/* 맞춤 추천 이유 (한 줄 요약) */}
            <section className="mt-6">
              <h3 className="flex items-center gap-1.5 text-section text-ink">
                <Sparkles size={19} className="text-brand fill-brand/10" /> 맞춤 추천 이유
              </h3>
              <div className="mt-3 rounded-2xl bg-surface p-4 shadow-card border-l-4 border-brand">
                <MatchVerdict
                  eligibilityStatus={explanation.eligibility_status}
                  preferenceMatch={explanation.preference_match}
                  confidence={explanation.confidence}
                />
                <p className="text-[15px] font-bold leading-relaxed text-ink">
                  {explanation.summary}
                </p>
                <p className="mt-2 text-[11px] font-medium text-subtle">
                  {explanation.generated_by === 'gemini'
                    ? '규칙 판정을 기준으로 AI가 설명 문장을 정리했어요.'
                    : '공고에서 구조화한 조건을 규칙으로 자동 대조했어요.'}
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
                    <div key={strength} className="flex items-start gap-2 rounded-2xl bg-surface p-3.5 shadow-card">
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

            {explanation.evidence.length > 0 && (
              <section className="mt-6">
                <h3 className="flex items-center gap-1.5 text-section text-ink">
                  <FileText size={19} className="text-brand" /> 판정에 사용한 공고 근거
                </h3>
                <div className="mt-3 space-y-2 rounded-2xl bg-white p-4 shadow-card">
                  {explanation.evidence.map((item) => (
                    <p key={item} className="text-sm leading-relaxed text-muted">
                      • {item}
                    </p>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        <Section title="지원 대상" content={policy.target_text} />
        <Section title="자격 조건" content={eligibilityText} />
        <Section title="지원 내용" content={policy.support_content || policy.body} />
        <Section title="신청 방법" content={applicationMethodText} />
        <Section title="필요 서류" content={documentList(policy.required_documents)} />
        <Section title="문의처" content={contactText} />

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
                  className="flex items-center gap-2 rounded-2xl bg-surface p-3.5 shadow-card hover:bg-black/[0.01] active:scale-[0.99] transition-transform duration-100"
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

        <div className="mt-6 flex items-start gap-2 rounded-2xl bg-blue-50/70 p-4 text-xs leading-relaxed text-muted">
          <ShieldCheck size={17} className="mt-0.5 shrink-0 text-brand" />
          <p>
            맞춤 판정은 입력한 프로필과 공고문에서 구조화한 조건을 대조한 참고 안내예요.
            최종 신청 전에는 신청 페이지와 담당 기관에서 자격·마감·제출 서류를 확인해 주세요.
          </p>
        </div>
      </div>

      <div className="space-y-2 border-t border-line bg-cream px-5 py-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate(`/chat?policyId=${policy.id}`)}
            className="flex h-12 items-center justify-center gap-1.5 rounded-xl border border-line bg-white text-[15px] font-bold text-ink transition-colors active:bg-line/40"
          >
            <MessageCircle size={16} strokeWidth={1.9} /> AI 상담
          </button>
          <AddToCalendarButton policyId={policy.id} applyEnd={policy.apply_end} variant="full" />
        </div>
        <button
          disabled={!policy.apply_url}
          onClick={() => policy.apply_url && window.open(policy.apply_url, '_blank', 'noopener,noreferrer')}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary text-[15px] font-bold text-white transition-colors active:bg-primary-hover disabled:bg-line disabled:text-subtle"
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

/**
 * 공고 본문 섹션.
 *
 * 예전에는 원문을 whitespace-pre-line으로 그대로 뿌렸다. PDF·HWP에서 뽑은 텍스트라
 * 문장이 중간에서 끊기고 빈 줄이 서너 개씩 이어져 읽기가 어려웠다.
 * 다듬은 뒤, 긴 건 앞부분만 보여주고 나머지는 접는다.
 */
function Section({ title, content }: { title: string; content?: string | null }) {
  const [expanded, setExpanded] = useState(false)

  const text = cleanPolicyText(content)
  if (!text) return null

  const preview = truncateAtSentence(text)
  const isLong = preview !== text

  return (
    <section className="mt-6">
      <h3 className="text-section text-ink">{title}</h3>
      <p className="mt-2 whitespace-pre-line text-[15px] leading-[1.7] text-muted">
        {expanded || !isLong ? text : preview}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 flex h-11 items-center gap-1 text-sm font-semibold text-primary"
        >
          {expanded ? '접기' : '원문 더 보기'}
          <ChevronDown
            size={15}
            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </button>
      )}
    </section>
  )
}

function MatchVerdict({
  eligibilityStatus,
  preferenceMatch,
  confidence,
}: {
  eligibilityStatus: RecommendationExplanationResponse['eligibility_status']
  preferenceMatch: RecommendationExplanationResponse['preference_match']
  confidence: RecommendationExplanationResponse['confidence']
}) {
  const config = {
    eligible: {
      label: '자격 조건상 잘 맞음',
      description: '입력 정보와 확인된 공고 조건이 일치해요.',
      className: 'bg-brand-light/20 text-brand',
    },
    needs_review: {
      label: '추가 확인 필요',
      description: '공고에서 확정하지 못한 조건이 있어요.',
      className: 'bg-blue-50 text-muted',
    },
    ineligible: {
      label: '현재 조건과 불일치',
      description: '입력 정보 기준으로 맞지 않는 조건이 있어요.',
      className: 'bg-red-50 text-red-700',
    },
  }[eligibilityStatus]
  const confidenceLabel = { high: '자동 확인 수준 높음', medium: '자동 확인 수준 보통', low: '자동 확인 수준 낮음' }[
    confidence
  ]
  const preferenceLabel = {
    exact: '관심 분야 일치',
    partial: '관심 분야 일부 일치',
    none: '관심 분야 불일치',
    not_requested: null,
  }[preferenceMatch]

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-line pb-3">
      <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${config.className}`}>
        {config.label}
      </span>
      {preferenceLabel && (
        <span className="rounded-full bg-line/60 px-2.5 py-1 text-xs font-bold text-muted">
          {preferenceLabel}
        </span>
      )}
      <span className="text-xs font-medium text-muted">{config.description}</span>
      <span className="ml-auto text-[11px] text-subtle">{confidenceLabel}</span>
    </div>
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
    .map((name) => `• ${name}`)
    .join('\n')
}

const APPLICATION_METHOD_LABELS: Record<string, string> = {
  online: '온라인 접수',
  visit: '방문 접수',
  mail: '우편 접수',
  email: '이메일 접수',
  fax: '팩스 접수',
  e_document: '전자문서 접수',
}

const INDUSTRY_LABELS: Record<string, string> = {
  restaurant: '음식점업',
  manufacturing: '제조업',
  retail: '도소매업',
  tourism: '관광·숙박업',
  market: '전통시장·상점가',
  export: '수출·해외진출',
  digital: '디지털·온라인',
  agriculture_fishery_forestry: '농림수산업',
  information_communication: '정보통신업',
  other_business: '기타 업종',
  company_other_business: '기타 기업',
}

function formatApplicationMethods(methods: string[]) {
  if (methods.length === 0) return null
  return [...new Set(methods.map((method) => APPLICATION_METHOD_LABELS[method] || method))]
    .map((method) => `• ${method}`)
    .join('\n')
}

function formatContactPoints(points: unknown[]) {
  const values = points
    .map((point) => {
      if (typeof point === 'string') return point.trim()
      if (point && typeof point === 'object') {
        const record = point as Record<string, unknown>
        return String(record.phone || record.value || record.contact || '').trim()
      }
      return ''
    })
    .filter(Boolean)
  const unique = [...new Set(values)]
  if (unique.length === 0) return null
  const visible = unique.slice(0, 5).map((contact) => `• ${contact}`)
  if (unique.length > 5) visible.push(`• 그 외 ${unique.length - 5}개 문의처는 공고문에서 확인`)
  return visible.join('\n')
}

function formatEligibility(eligibility: Record<string, unknown>) {
  const lines: string[] = []
  addConditionSource(lines, eligibility.employee_limit, '직원수')
  addConditionSource(lines, eligibility.sales_limit, '연매출')
  addConditionSource(lines, eligibility.business_age_limit, '업력')

  const industry = asRecord(eligibility.industry_condition)
  if (industry?.mode === 'unrestricted') {
    lines.push('업종: 제한 없음')
  } else if (industry) {
    const excluded = stringList(industry.exclude_tags)
    if (excluded.length > 0) {
      lines.push(`제외 업종: ${excluded.map((tag) => INDUSTRY_LABELS[tag] || tag).join(', ')}`)
    }

    const evidence = Array.isArray(industry.evidence) ? industry.evidence.map(asRecord).filter(Boolean) : []
    const hasTextEvidence = evidence.some(
      (item) => item?.source_text && item.source_text !== 'gov24_support_condition_code',
    )
    const included = stringList(industry.include_tags)
    if (hasTextEvidence && included.length > 0) {
      lines.push(`대상 업종: ${included.map((tag) => INDUSTRY_LABELS[tag] || tag).join(', ')}`)
    }
  }

  const selectionCriteria = eligibility.selection_criteria
  if (typeof selectionCriteria === 'string' && selectionCriteria.trim()) {
    lines.push(`선정 기준: ${selectionCriteria.trim()}`)
  }

  return lines.length > 0 ? lines.map((line) => `• ${line}`).join('\n') : null
}

function addConditionSource(lines: string[], value: unknown, label: string) {
  const record = asRecord(value)
  const sourceText = record?.source_text
  if (typeof sourceText === 'string' && sourceText.trim()) {
    lines.push(`${label}: ${sourceText.trim()}`)
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function stringList(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}
