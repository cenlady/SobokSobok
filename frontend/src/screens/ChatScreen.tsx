import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ChevronDown, LoaderCircle, Send, X } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import TopBar from '../components/TopBar'
import assistantBotIcon from '../assets/sobok-assistant-bot.png'
import { Panel } from '../components/ui'
import { apiFetch } from '../lib/api'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type { ChatAnswerResponse, ChatChunkSource, RecommendationPreviewResponse } from '../types'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  sources?: ChatChunkSource[]
  policies?: PolicyCardData[]
  pending?: boolean
}

interface PolicyContext {
  title: string
}

const QUICK = ['내 조건에 맞는 지원 정책 찾기', '전기요금 지원 정책 확인', '신청 서류가 필요한 정책 확인']

const DETAIL_QUICK = ['지원 대상 확인', '필요 서류 확인', '신청 기간 확인']

const initialMessages: Message[] = [
  {
    id: 1,
    role: 'bot',
    text: '정책명, 지원 대상, 신청 서류처럼 확인할 내용을 입력해 주세요.',
  },
]

function initialMessagesFor(policyId: string | null): Message[] {
  return policyId
    ? [
        {
          id: 1,
          role: 'bot',
          text: '선택한 공고문을 기준으로 지원 대상, 신청 기간, 필요 서류와 접수 방법을 확인합니다.',
        },
      ]
    : initialMessages
}

export default function ChatScreen() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const policyId = searchParams.get('policyId')
  const { profile } = useProfile()
  const { has, toggle } = useSavedPolicies()
  const [messages, setMessages] = useState<Message[]>(() => initialMessagesFor(policyId))
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [pendingSave, setPendingSave] = useState<string | null>(null)
  const [policyContext, setPolicyContext] = useState<PolicyContext | null>(null)
  const nextId = useRef(2)
  const messageScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const container = messageScrollRef.current
      if (!container) return
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    })

    return () => window.cancelAnimationFrame(frame)
  }, [messages])

  useEffect(() => {
    setMessages(initialMessagesFor(policyId))
    setInput('')
    setSending(false)
    nextId.current = 2
  }, [policyId])

  useEffect(() => {
    setPolicyContext(null)
    if (!policyId) return

    let ignore = false
    apiFetch<PolicyContext>(`/api/v1/policies/normalized/${encodeURIComponent(policyId)}`)
      .then((policy) => {
        if (!ignore) setPolicyContext(policy)
      })
      .catch(() => {
        if (!ignore) setPolicyContext({ title: '선택한 공고문' })
      })

    return () => {
      ignore = true
    }
  }, [policyId])

  const push = (m: Omit<Message, 'id'>) => {
    const id = nextId.current++
    setMessages((prev) => [...prev, { ...m, id }])
    return id
  }

  const replace = (id: number, next: Omit<Message, 'id'>) => {
    setMessages((prev) => prev.map((message) => (message.id === id ? { ...next, id } : message)))
  }

  const askChatbot = async (query: string) => {
    if (!policyId && isRecommendationRequest(query)) {
      await askRecommendations()
      return
    }

    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: policyId
        ? '공고문에서 답변에 필요한 내용을 확인하고 있습니다.'
        : '정책 문서에서 관련 내용을 확인하고 있습니다.',
      pending: true,
    })

    try {
      const path = policyId
        ? `/api/v1/chat/ask?policy_id=${encodeURIComponent(policyId)}`
        : '/api/v1/chat/ask'
      const data = await apiFetch<ChatAnswerResponse>(
        path,
        {
          method: 'POST',
          json: { query, limit: 6 },
        },
      )
      replace(pendingId, {
        role: 'bot',
        text: data.answer || '공고문에서 답변을 찾지 못했어요. 질문을 조금 더 구체적으로 입력해주세요.',
        sources: data.sources,
      })
    } catch (error) {
      const detail = error instanceof Error ? error.message : ''
      replace(pendingId, {
        role: 'bot',
        text: detail === '정책을 찾을 수 없습니다.' || detail.includes('로그인')
          ? detail
          : '정책 내용을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const askRecommendations = async () => {
    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: '입력한 사업장 정보를 기준으로 맞춤 정책을 확인하고 있습니다.',
      pending: true,
    })

    try {
      const data = await apiFetch<RecommendationPreviewResponse>(
        '/api/v1/recommend/preview?limit=3',
        {
          method: 'POST',
          json: buildRecommendationRequest(profile),
        },
      )
      const policies = data.results.map((item) => ({
        policy_id: item.policy_id,
        title: item.title,
        summary: item.summary,
        support_type: item.support_type,
        apply_end: item.apply_end,
        rank_score: item.rank_score,
        eligibility_status: item.eligibility_status,
        preference_match: item.preference_match,
        match_status: item.match_status,
        reasons: item.reasons,
        warnings: item.warnings,
        unmet_conditions: item.unmet_conditions,
      }))
      replace(pendingId, {
        role: 'bot',
        text: policies.length > 0
          ? `입력한 조건과 가까운 정책 ${policies.length}건을 확인했습니다. 정책을 누르면 지원 대상과 필요 서류를 이어서 확인할 수 있습니다.${data.profile_warnings?.[0] ? `\n\n입력 정보 확인: ${data.profile_warnings[0]}` : ''}`
          : '현재 입력 정보로 추천할 정책을 찾지 못했습니다. 마이페이지에서 업종, 지역, 매출 정보를 확인해 주세요.',
        policies,
      })
    } catch {
      replace(pendingId, {
        role: 'bot',
        text: '맞춤 정책을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const send = (text: string) => {
    const t = text.trim()
    if (!t || sending) return
    push({ role: 'user', text: t })
    setInput('')
    void askChatbot(t)
  }

  const handleToggleSave = async (targetPolicyId: string) => {
    setPendingSave(targetPolicyId)
    try {
      await toggle(targetPolicyId)
    } finally {
      setPendingSave(null)
    }
  }

  const lastMessage = messages[messages.length - 1]
  const showQuickQuestions = !sending && lastMessage?.role === 'bot' && !lastMessage.pending

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <h1 className="sr-only">정책 도우미</h1>

      <div
        ref={messageScrollRef}
        className="no-scrollbar min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 pb-5 pt-1"
      >
        {policyId && (
          <section className="rounded-2xl bg-brand-dark p-4 text-white shadow-card">
            <div className="flex items-start gap-3">
              <button
                type="button"
                onClick={() => navigate(`/policy/${policyId}`)}
                className="min-w-0 flex-1 text-left outline-none focus-visible:rounded-lg focus-visible:ring-2 focus-visible:ring-white/50"
              >
                <span className="block text-[11px] font-medium text-white/70">현재 확인 중인 정책</span>
                <span className="mt-1 block line-clamp-2 text-[15px] font-bold leading-snug">
                  {policyContext?.title || '정책 정보를 불러오는 중'}
                </span>
              </button>
              <button
                type="button"
                onClick={() => navigate('/chat', { replace: true })}
                aria-label="선택한 정책 닫기"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10 text-white outline-none transition-colors active:bg-white/20 focus-visible:ring-2 focus-visible:ring-white/50"
              >
                <X size={18} />
              </button>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-white/75">
              이 대화는 선택한 공고문을 기준으로 답변합니다.
            </p>
          </section>
        )}

        {messages.map((m) =>
          m.role === 'bot' ? (
            <BotBubble
              key={m.id}
              m={m}
              navigate={navigate}
              has={has}
              onToggleSave={handleToggleSave}
              pendingSave={pendingSave}
              detailMode={Boolean(policyId)}
            />
          ) : (
            <div key={m.id} className="flex justify-end">
              <p className="max-w-[82%] whitespace-pre-line rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-sm font-semibold leading-relaxed text-white shadow-card">
                {m.text}
              </p>
            </div>
          ),
        )}

        {showQuickQuestions && (
          <section className="flex flex-wrap gap-2 pt-1" aria-label="추천 질문">
            {(policyId ? DETAIL_QUICK : QUICK).map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => send(question)}
                className="min-h-11 rounded-full border border-line bg-surface px-4 py-2 text-left text-[13px] font-semibold leading-snug text-ink outline-none transition-colors active:bg-line/40 focus-visible:ring-2 focus-visible:ring-primary/20"
              >
                {question}
              </button>
            ))}
          </section>
        )}
      </div>

      <div className="border-t border-line bg-cream px-3 pb-3 pt-2">
        <p className="mb-1.5 text-center text-[11px] leading-relaxed text-subtle">
          답변은 공고문을 자동으로 정리한 참고 내용입니다.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex h-14 items-center rounded-full border border-line bg-surface p-1.5 pl-5 shadow-card transition-colors focus-within:border-primary/40"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="확인할 내용을 입력하세요"
            aria-label="정책 질문"
            className="min-w-0 flex-1 bg-transparent pr-2 text-[15px] text-ink outline-none placeholder:text-subtle"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="질문 보내기"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-white outline-none transition-colors active:bg-primary-hover disabled:bg-line disabled:text-subtle focus-visible:ring-2 focus-visible:ring-primary/25"
          >
            {sending ? <LoaderCircle size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  )
}

function BotBubble({
  m,
  navigate,
  has,
  onToggleSave,
  pendingSave,
  detailMode,
}: {
  m: Message
  navigate: ReturnType<typeof useNavigate>
  has: (id: string) => boolean
  onToggleSave: (policyId: string) => void
  pendingSave: string | null
  detailMode: boolean
}) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  const uniqueSources = m.sources
    ? detailMode
      ? uniqueSourcesByDocument(m.sources)
      : uniqueSourcesByPolicy(m.sources)
    : []
  const visibleSources = uniqueSources.slice(0, 3)
  const displayText = cleanChatDisplayText(m.text || '')

  return (
    <div className="space-y-2">
      {displayText && (
        <div className="flex items-start gap-2">
          <span
            aria-hidden="true"
            className="flex h-[52px] w-[52px] shrink-0 items-center justify-center"
          >
            <img
              src={assistantBotIcon}
              alt=""
              className="h-[52px] w-[52px] object-contain"
            />
          </span>
          <div
            aria-label="소복소복 답변"
            className="max-w-[calc(100%-60px)] rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3 shadow-card"
          >
            {m.pending && (
              <LoaderCircle size={17} className="mr-2 inline-block animate-spin text-muted" />
            )}
            <p className="inline whitespace-pre-line text-sm leading-[1.75] text-ink">{displayText}</p>
          </div>
        </div>
      )}

      {visibleSources.length > 0 && (
        <div className="ml-[60px] overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
          <button
            type="button"
            onClick={() => setSourcesExpanded((expanded) => !expanded)}
            aria-expanded={sourcesExpanded}
            className="flex min-h-11 w-full items-center justify-between gap-3 px-4 text-left outline-none transition-colors active:bg-line/30 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/20"
          >
            <span className="text-xs font-bold text-muted">답변 근거 {visibleSources.length}건</span>
            <span className="flex items-center gap-1 text-xs font-bold text-brand">
              {sourcesExpanded ? '접기' : '보기'}
              <ChevronDown
                size={14}
                className={`transition-transform ${sourcesExpanded ? 'rotate-180' : ''}`}
              />
            </span>
          </button>

          {sourcesExpanded && (
            <div className="space-y-2 border-t border-line p-3">
              {visibleSources.map((source) => (
                <button
                  key={source.chunk_id}
                  type="button"
                  onClick={() => navigate(`/policy/${source.policy_id}`)}
                  className="w-full rounded-xl bg-cream/70 p-3 text-left outline-none transition-colors active:bg-line/40 focus-visible:ring-2 focus-visible:ring-primary/20"
                >
                  <span className="block line-clamp-2 text-[13px] font-semibold leading-snug text-ink">
                    {source.policy_title || source.document_title || '공고문'}
                  </span>
                  <span className="mt-1 block text-[11px] font-medium text-subtle">
                    {documentTypeLabel(source.document_type)}
                    {source.source_ref ? ` · ${source.source_ref}` : ''}
                  </span>
                  <span className="mt-1.5 block line-clamp-2 text-xs leading-relaxed text-muted">
                    {source.chunk_text}
                  </span>
                  <span className="mt-2 flex items-center gap-1 text-xs font-bold text-brand">
                    정책 상세 보기 <ArrowRight size={13} />
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {m.policies && m.policies.length > 0 && (
        <Panel divided className="ml-[60px]">
          {m.policies.map((policy) => (
            <PolicyCard
              key={policy.policy_id}
              policy={policy}
              saved={has(policy.policy_id)}
              onToggleSave={onToggleSave}
              savePending={pendingSave === policy.policy_id}
            />
          ))}
        </Panel>
      )}
    </div>
  )
}

function cleanChatDisplayText(value: string) {
  return value
    .replace(/^\s*---+\s*$/gm, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function isRecommendationRequest(text: string) {
  const normalized = text.trim().toLowerCase()
  const recommendationSignals = [
    '추천',
    '찾아줘',
    '찾아 줘',
    '받을 수',
    '내가 받을',
    '맞는',
  ]
  const policyDomainSignals = [
    '정책',
    '공고',
    '지원',
    '지원금',
    '보조금',
    '혜택',
    '대출',
    '융자',
    '보증',
    '소상공인',
    '사업자',
    '자영업',
    '업종',
    '매출',
  ]

  const hasRecommendationSignal = recommendationSignals.some((keyword) => normalized.includes(keyword))
  const hasPolicyDomainSignal = policyDomainSignals.some((keyword) => normalized.includes(keyword))
  return hasRecommendationSignal && hasPolicyDomainSignal
}

function uniqueSourcesByPolicy(sources: ChatChunkSource[]) {
  const seen = new Set<string>()
  return sources.filter((source) => {
    if (seen.has(source.policy_id)) return false
    seen.add(source.policy_id)
    return true
  })
}

function uniqueSourcesByDocument(sources: ChatChunkSource[]) {
  const seen = new Set<string>()
  return sources.filter((source) => {
    const key = source.document_id || source.chunk_id
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function documentTypeLabel(value?: string | null) {
  const labels: Record<string, string> = {
    summary: '정책 요약',
    support_content: '지원 내용',
    eligibility: '지원 대상·자격',
    application: '신청 방법',
    deadline: '신청 기간',
    requirements: '필요 서류',
    contact: '문의처',
    procedure: '선정 절차',
    reference: '참고 자료',
    body: '공고문 본문',
    section: '공고문 세부 내용',
  }
  return value ? labels[value] || value : '공고문 근거'
}
