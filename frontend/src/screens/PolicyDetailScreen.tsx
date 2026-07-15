import { useEffect, useState } from 'react'
import {
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  Check,
  MessageCircle,
  CalendarDays,
  ChevronDown,
  Info,
  MapPin,
  Tag,
  Paperclip,
  FileText,
  Download,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import AddToCalendarButton from '../components/AddToCalendarButton'
import BottomNav from '../components/BottomNav'
import { API_BASE_URL, apiFetch } from '../lib/api'
import { formatPeriod, getDeadlineInfo } from '../lib/deadline'
import { cleanPolicyText, truncateAtSentence } from '../lib/text'
import { Button, IconButton, Notice, Panel, ScreenHeader, StatusBadge } from '../components/ui'
import { useSavedPolicies, useProfile } from '../lib/storage'
import { buildRecommendationRequest } from '../lib/recommend'
import type {
  PolicyDetailResponse,
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
  const { has, toggle } = useSavedPolicies()
  const [savePending, setSavePending] = useState(false)
  const { profile, loading: profileLoading } = useProfile()
  const [policy, setPolicy] = useState<PolicyDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<RecommendationExplanationResponse | null>(null)
  const [explanationError, setExplanationError] = useState<string | null>(null)

  useEffect(() => {
    if (!policyId) return
    let ignore = false
    setLoading(true)
    setError(null)
    setPolicy(null)
    setExplanation(null)
    setExplanationError(null)

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
    setExplanationError(null)
    // apiFetch를 써야 JWT가 붙는다. /recommend는 인증 가드가 걸려 있어
    // 날것의 fetch로는 401이 나고 설명이 통째로 사라진다.
    requestExplanation(policyId, buildRecommendationRequest(profile))
      .then((data) => {
        if (!ignore) setExplanation(data)
      })
      .catch((err) => {
        if (!ignore) {
          setExplanationError(
            err instanceof Error
              ? err.message
              : 'AI 추천 설명을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.',
          )
        }
      })
    return () => {
      ignore = true
    }
  }, [policyId, policy, profile, profileLoading])

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
    return <PolicyDetailSkeleton />
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
      <ScreenHeader
        title="정책 상세"
        onBack={() => navigate(-1)}
        action={
          <IconButton
            icon={isSaved ? BookmarkCheck : Bookmark}
            onClick={toggleSave}
            disabled={savePending}
            active={isSaved}
            label={isSaved ? '저장 해제' : '정책 저장'}
          />
        }
      />

      <div className="no-scrollbar flex-1 overflow-y-auto px-5 pb-6">
        {/* 상태 배지는 하나. 예전에는 유형·점수·status 원시값(open/notice)이 나란히
            붙어 있었고, 특히 status는 DB 값이 그대로 화면에 노출되고 있었다. */}
        <StatusBadge info={getDeadlineInfo(policy)} />

        <h2
          className={`mt-3 break-keep tracking-[-0.02em] text-ink [overflow-wrap:anywhere] ${policyTitleClass(
            policy.title,
          )}`}
        >
          {policy.title}
        </h2>
        {policy.organization && (
          <p className="mt-1.5 text-[13px] font-medium text-muted">{policy.organization}</p>
        )}
        {policy.summary && (
          <p className="surface-panel mt-4 p-4 text-[15px] leading-relaxed text-muted">
            {policy.summary}
          </p>
        )}

        <Panel className="mt-5 space-y-3 p-5">
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
        </Panel>

        {!explanation && !explanationError && <ExplanationLoadingPanel />}

        {explanationError && (
          <Notice tone="error" className="mt-6" title="AI 조건 비교를 완료하지 못했어요">
            {explanationError}
          </Notice>
        )}

        {explanation && (
          <section className="mt-6">
            <h3 className="text-section text-ink">조건 비교 결과</h3>
            <Panel divided className="mt-3">
              <div className="p-4">
                <MatchVerdict
                  eligibilityStatus={explanation.eligibility_status}
                  preferenceMatch={explanation.preference_match}
                  confidence={explanation.confidence}
                />
                <p className="text-[15px] font-semibold leading-relaxed text-ink">
                  {explanation.summary}
                </p>
              </div>
              <ResultGroup title="확인된 조건" items={explanation.strengths} tone="success" />
              <ResultGroup title="추가 확인 사항" items={explanation.aspects_to_check} />
              <ResultGroup title="다음 단계" items={explanation.next_actions} tone="action" />
              <EvidenceResultGroup items={explanation.evidence} />
            </Panel>
            <p className="mt-2 text-[11px] leading-relaxed text-subtle">
              공고문과 입력 정보를 바탕으로 자동 정리한 참고 안내입니다.
            </p>
          </section>
        )}

        <section className="mt-6">
          <h3 className="text-section text-ink">공고 안내</h3>
          <Panel divided className="mt-3">
            <Section title="지원 대상" content={policy.target_text} />
            <Section title="자격 조건" content={eligibilityText} />
            <Section title="지원 내용" content={policy.support_content || policy.body} />
            <Section title="신청 방법" content={applicationMethodText} />
            <Section title="필요 서류" content={documentList(policy.required_documents)} />
            <Section title="문의처" content={contactText} />
          </Panel>
        </section>

        {policy.attachments && policy.attachments.length > 0 && (
          <section className="mt-6">
            <h3 className="text-section text-ink flex items-center gap-1.5">
              <Paperclip size={18} className="text-brand" /> 첨부 파일
            </h3>
            <Panel divided className="mt-3">
              {policy.attachments.map((file) => (
                <a
                  key={file.attachment_file_id}
                  href={`${API_BASE_URL}/api/v1/policies/attachments/${file.attachment_file_id}/download`}
                  download={file.original_file_name || 'attachment'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex min-h-12 items-center gap-2 p-3.5 transition-colors active:bg-line/40"
                >
                  <FileText size={18} className="text-brand flex-shrink-0" />
                  <span className="text-[14px] font-semibold truncate flex-1 text-ink">
                    {file.original_file_name || '첨부파일'}
                  </span>
                  <Download size={16} className="text-subtle flex-shrink-0" />
                </a>
              ))}
            </Panel>
          </section>
        )}

        <Notice className="mt-4" title="신청 전 확인">
          최종 신청 전에는 신청 페이지와 담당 기관에서 자격, 마감일, 제출 서류를 확인해
          주세요.
        </Notice>
      </div>

      <div className="border-t border-line bg-cream/95 px-5 py-3 backdrop-blur">
        <div className="grid grid-cols-3 gap-2">
          <Button
            onClick={() => navigate(`/chat?policyId=${policy.id}`)}
            variant="secondary"
            size="sm"
            full
          >
            <MessageCircle size={16} strokeWidth={1.9} /> 도우미
          </Button>
          <AddToCalendarButton policyId={policy.id} applyEnd={policy.apply_end} variant="full" />
          <Button
            disabled={!policy.apply_url}
            onClick={() =>
              policy.apply_url && window.open(policy.apply_url, '_blank', 'noopener,noreferrer')
            }
            size="sm"
            full
          >
            신청하기 <ArrowRight size={17} />
          </Button>
        </div>
      </div>
      <BottomNav />
    </div>
  )
}

function StateScreen({ label }: { label: string }) {
  const navigate = useNavigate()
  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      <ScreenHeader title="정책 상세" onBack={() => navigate(-1)} />
      <div className="flex flex-1 items-center px-5">
        <Notice tone="error" className="w-full" title="정책 정보를 확인하지 못했습니다">
          <p>{label}</p>
          <Button variant="secondary" size="sm" onClick={() => navigate('/')} className="mt-3">
            홈으로
          </Button>
        </Notice>
      </div>
    </div>
  )
}

function policyTitleClass(title: string) {
  const length = title.trim().length
  if (length >= 60) return 'text-[18px] font-semibold leading-[1.45]'
  if (length >= 36) return 'text-[20px] font-bold leading-[1.4]'
  return 'text-[22px] font-bold leading-[1.35]'
}

function PolicyDetailSkeleton() {
  const navigate = useNavigate()
  return (
    <div className="app-frame flex h-[100dvh] flex-col bg-cream">
      <ScreenHeader title="정책 상세" onBack={() => navigate(-1)} />
      <div className="flex-1 overflow-hidden px-5 pb-6">
        <div className="animate-pulse">
          <div className="h-5 w-14 rounded-md bg-line" />
          <div className="mt-4 h-7 w-full rounded-lg bg-line/80" />
          <div className="mt-2 h-7 w-3/4 rounded-lg bg-line/80" />
          <div className="mt-3 h-4 w-36 rounded bg-line/70" />
          <div className="surface-panel mt-5 space-y-3 p-4">
            <div className="h-4 w-full rounded bg-line/70" />
            <div className="h-4 w-4/5 rounded bg-line/70" />
          </div>
          <div className="surface-panel mt-5 space-y-4 p-5">
            <div className="h-4 w-3/4 rounded bg-line/70" />
            <div className="h-4 w-2/3 rounded bg-line/70" />
            <div className="h-4 w-4/5 rounded bg-line/70" />
          </div>
        </div>
      </div>
      <div className="border-t border-line bg-cream px-5 py-3">
        <div className="h-12 animate-pulse rounded-xl bg-line/70" />
      </div>
      <BottomNav />
    </div>
  )
}

function ExplanationLoadingPanel() {
  return (
    <section className="mt-6">
      <h3 className="text-section text-ink">조건 비교 결과</h3>
      <Panel divided className="mt-3">
        <div className="p-4">
          <p className="text-sm font-semibold text-ink">조건을 확인하고 있습니다</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            입력 정보와 공고 조건을 항목별로 비교합니다.
          </p>
        </div>
        <div className="animate-pulse space-y-3 p-4" aria-hidden="true">
          <div className="h-3 w-20 rounded bg-line" />
          <div className="h-4 w-full rounded bg-line/70" />
          <div className="h-4 w-4/5 rounded bg-line/70" />
        </div>
        <div className="animate-pulse space-y-3 p-4" aria-hidden="true">
          <div className="h-3 w-24 rounded bg-line" />
          <div className="h-4 w-5/6 rounded bg-line/70" />
        </div>
      </Panel>
    </section>
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
    <section className="p-4">
      <h3 className="text-[15px] font-bold text-ink">{title}</h3>
              <p className="mt-1.5 whitespace-pre-line text-[15px] leading-[1.7] text-muted">
        {expanded || !isLong ? text : preview}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-1.5 flex h-11 items-center gap-1 rounded-lg text-sm font-semibold text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
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

function ResultGroup({
  title,
  items,
  tone = 'neutral',
}: {
  title: string
  items: string[]
  tone?: 'neutral' | 'success' | 'action'
}) {
  if (items.length === 0) return null

  const marker = {
    neutral: 'bg-line text-muted',
    success: 'bg-status-green/10 text-status-green',
    action: 'bg-primary-soft text-primary',
  }[tone]
  const MarkerIcon = {
    neutral: Info,
    success: Check,
    action: ArrowRight,
  }[tone]

  return (
    <div className="p-4">
      <p className="text-[13px] font-bold text-muted">{title}</p>
      <ul className="mt-2.5 space-y-2.5">
        {items.map((item) => (
        <li key={item} className="flex items-start gap-2.5 text-[15px] leading-relaxed text-muted">
            <span
              aria-hidden="true"
              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${marker}`}
            >
              <MarkerIcon size={11} strokeWidth={2.75} />
            </span>
            <span>{item.replace(/^-\s*/, '')}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function EvidenceResultGroup({ items }: { items: string[] }) {
  const [expanded, setExpanded] = useState(false)

  if (items.length === 0) return null

  return (
    <div>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        className="flex min-h-14 w-full items-center justify-between gap-3 p-4 text-left transition-colors active:bg-line/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/20"
      >
        <span className="text-xs font-bold text-muted">판정에 사용한 공고 근거</span>
        <span className="flex shrink-0 items-center gap-1.5 text-subtle">
          <span className="text-[11px]">{items.length}개</span>
          <ChevronDown
            size={16}
            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </span>
      </button>
      {expanded && (
        <div className="border-t border-line p-4 pt-3">
          <ul className="space-y-2.5">
            {items.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-[15px] leading-relaxed text-muted">
                <span
                  aria-hidden="true"
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-line text-muted"
                >
                  <Info size={11} strokeWidth={2.25} />
                </span>
                <span>{item.replace(/^\-\s*/, '')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
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
      description: '입력 정보와 확인된 공고 조건이 일치합니다.',
      className: 'bg-status-green/10 text-status-green',
    },
    needs_review: {
      label: '추가 확인 필요',
      description: '공고에서 확정하지 못한 조건이 있습니다.',
      className: 'bg-accent-soft text-brand',
    },
    ineligible: {
      label: '현재 조건과 불일치',
      description: '입력 정보 기준으로 맞지 않는 조건이 있습니다.',
      className: 'bg-status-red/10 text-status-red',
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
      <span className="text-[13px] font-medium text-muted">{config.description}</span>
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
