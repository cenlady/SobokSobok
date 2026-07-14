import { useRef, useState } from 'react'
import { ArrowRight, Bot, LoaderCircle, Plus, Send } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import TopBar from '../components/TopBar'
import { apiFetch } from '../lib/api'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type { ChatAnswerResponse, ChatChunkSource, RecommendationPreviewResponse } from '../types'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  time?: string
  sources?: ChatChunkSource[]
  policies?: PolicyCardData[]
  pending?: boolean
}

const QUICK = ['내가 받을 수 있는 지원금 찾아줘', '소상공인 전기요금 지원 알려줘', '신청 서류가 필요한 정책 알려줘']

const DETAIL_QUICK = ['지원 대상이 누구야?', '필요한 서류가 뭐야?', '신청 기간은 언제까지야?']

const initialMessages: Message[] = [
  {
    id: 1,
    role: 'bot',
    text: '안녕하세요 사장님! 오늘도 소복소복 쌓이는 소식들을 전해드릴게요.\n궁금하신 정책이나 지원금이 있으신가요?',
    time: '오전 10:05',
  },
]

export default function ChatScreen() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const policyId = searchParams.get('policyId')
  const { profile } = useProfile()
  const { has, toggle } = useSavedPolicies()
  const [messages, setMessages] = useState<Message[]>(() =>
    policyId
      ? [
          {
            id: 1,
            role: 'bot',
            text: '선택한 공고의 원문을 기준으로 답변해드릴게요. 지원 대상, 신청 기간, 필요 서류, 접수 방법 등을 물어보세요.',
          },
        ]
      : initialMessages,
  )
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [pendingSave, setPendingSave] = useState<string | null>(null)
  const nextId = useRef(2)

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
      text: policyId ? '공고문에서 답변 근거를 찾고 있어요.' : '정책 문서 전체에서 관련 근거를 찾고 있어요.',
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
          : '정책 상담 API를 호출하지 못했어요. 잠시 후 다시 시도해주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const askRecommendations = async () => {
    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: '사장님 프로필을 기준으로 맞춤 정책을 찾고 있어요.',
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
        match_status: item.match_status,
        reasons: item.reasons,
        warnings: item.warnings,
      }))
      replace(pendingId, {
        role: 'bot',
        text: policies.length > 0
          ? `사장님 조건과 가까운 정책 ${policies.length}건을 찾았어요. 각 정책을 눌러 상세 화면에서 지원 대상이나 서류를 이어서 물어볼 수 있어요.`
          : '지금 프로필 기준으로 바로 추천할 정책을 찾지 못했어요. 업종, 지역, 매출 정보를 조금 더 채워보면 추천 정확도가 올라가요.',
        policies,
      })
    } catch {
      replace(pendingId, {
        role: 'bot',
        text: '맞춤 추천 API를 호출하지 못했어요. 잠시 후 다시 시도해주세요.',
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

  return (
    <div className="flex h-full flex-col">
      <TopBar />

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {policyId && (
          <div className="rounded-2xl bg-primary p-4 text-white shadow-card">
            <p className="text-sm font-semibold">선택한 정책 상담을 이어갈 수 있어요.</p>
            <p className="mt-1 break-all text-xs text-white/70">policyId: {policyId}</p>
            <button
              onClick={() => navigate(`/policy/${policyId}`)}
              className="mt-3 rounded-xl bg-white px-3 py-2 text-xs font-bold text-ink"
            >
              정책 상세 다시 보기
            </button>
          </div>
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
            />
          ) : (
            <div key={m.id} className="flex justify-end">
              <p className="max-w-[78%] whitespace-pre-line rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-[15px] leading-relaxed text-white">
                {m.text}
              </p>
            </div>
          ),
        )}

        {/* 추천 질문 칩 */}
        <div className="flex flex-wrap gap-2 pt-1">
          {(policyId ? DETAIL_QUICK : QUICK).map((q) => (
            <button
              key={q}
              onClick={() => send(q)}
              disabled={sending}
              className="rounded-full border border-brand-light/40 bg-white px-4 py-2 text-sm font-medium text-ink active:bg-line/50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* 입력창 */}
      <div className="border-t border-line bg-cream px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2 rounded-full border border-brand-light/40 bg-white py-1.5 pl-2 pr-1.5"
        >
          <button type="button" className="p-2 text-subtle">
            <Plus size={22} />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요..."
            className="flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-subtle"
          />
          <button
            type="submit"
            disabled={sending}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white active:scale-95 disabled:opacity-50"
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
}: {
  m: Message
  navigate: ReturnType<typeof useNavigate>
  has: (id: string) => boolean
  onToggleSave: (policyId: string) => void
  pendingSave: string | null
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-ink">
        <Bot size={20} className="text-muted" />
      </span>
      <div className="max-w-[82%] space-y-2">
        {m.text && (
          <p className="whitespace-pre-line rounded-2xl rounded-tl-md bg-white px-4 py-3 text-[15px] leading-relaxed text-ink shadow-card">
            <span className="flex items-start gap-2">
              {m.pending && <LoaderCircle size={17} className="mt-0.5 flex-shrink-0 animate-spin" />}
              <span>{m.text}</span>
            </span>
          </p>
        )}
        {m.sources && m.sources.length > 0 && (
          <div className="rounded-2xl border border-brand-light/30 bg-white p-3 shadow-card">
            <p className="text-xs font-bold text-muted">답변 근거</p>
            <div className="mt-2 space-y-2">
              {uniqueSourcesByPolicy(m.sources).slice(0, 3).map((source) => (
                <div key={source.chunk_id} className="rounded-xl bg-cream px-3 py-2.5">
                  <p className="text-xs font-semibold text-muted">
                    {source.policy_title || source.document_title || '공고문'}
                  </p>
                  <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-muted">
                    {source.chunk_text}
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate(`/policy/${source.policy_id}`)}
                    className="mt-2 flex items-center gap-1 text-xs font-bold text-brand"
                  >
                    정책 상세 보기 <ArrowRight size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {m.policies && m.policies.length > 0 && (
          <div className="space-y-3">
            {m.policies.map((policy) => (
              <PolicyCard
                key={policy.policy_id}
                policy={policy}
                saved={has(policy.policy_id)}
                onToggleSave={onToggleSave}
                savePending={pendingSave === policy.policy_id}
              />
            ))}
          </div>
        )}
        {m.time && <p className="pl-1 text-xs text-subtle">{m.time}</p>}
      </div>
    </div>
  )
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
