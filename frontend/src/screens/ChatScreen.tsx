import { useRef, useState } from 'react'
import { ArrowRight, Bot, LoaderCircle, Plus, Send, X } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import TopBar from '../components/TopBar'
import { apiFetch } from '../lib/api'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type {
  ChatAnswerResponse,
  ChatChunkSource,
  ChatPolicyCandidate,
  ChatSessionResponse,
  RecommendationPreviewResponse,
} from '../types'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  time?: string
  sources?: ChatChunkSource[]
  candidates?: ChatPolicyCandidate[]
  policies?: PolicyCardData[]
  pending?: boolean
}

const QUICK = [
  '내게 맞는 지원 정책 추천해줘',
  '소상공인 전기요금 지원 공고를 찾아줘',
  '신청 서류가 필요한 정책을 알려줘',
]
const DETAIL_QUICK = ['지원 대상이 누구야?', '필요한 서류가 뭐야?', '신청 기간은 언제까지야?']

const initialMessages: Message[] = [
  {
    id: 1,
    role: 'bot',
    text: '안녕하세요, 사장님. 소복소복 정책 상담이에요.\n정책·공고의 대상, 지원 내용, 서류, 기간을 물어보거나 내게 맞는 정책 추천을 요청해 주세요.',
    time: '방금',
  },
]

function sessionStorageKey(policyId: string | null) {
  return policyId ? `sobok.chat.session.policy.${policyId}` : 'sobok.chat.session.main'
}

function policyStorageKey(policyId: string | null) {
  return policyId ? `sobok.chat.policy.policy.${policyId}` : 'sobok.chat.policy.main'
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // 브라우저 저장소를 쓸 수 없어도 현재 화면의 채팅은 계속 동작한다.
  }
}

function readStoredCandidate(policyId: string | null): ChatPolicyCandidate | null {
  const raw = readStorage(policyStorageKey(policyId))
  if (!raw) return null
  try {
    return JSON.parse(raw) as ChatPolicyCandidate
  } catch {
    return null
  }
}

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
            text: '선택한 공고문만 기준으로 답변할게요. 지원 대상, 신청 기간, 필요 서류, 신청 방법을 물어보세요.',
          },
        ]
      : initialMessages,
  )
  const [chatSessionId, setChatSessionId] = useState<string | null>(() => readStorage(sessionStorageKey(policyId)))
  const [sessionPolicy, setSessionPolicy] = useState<ChatPolicyCandidate | null>(() => readStoredCandidate(policyId))
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [selectingPolicyId, setSelectingPolicyId] = useState<string | null>(null)
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

  const persistSessionId = (sessionId: string) => {
    setChatSessionId(sessionId)
    writeStorage(sessionStorageKey(policyId), sessionId)
  }

  const persistSessionPolicy = (candidate: ChatPolicyCandidate | null) => {
    setSessionPolicy(candidate)
    writeStorage(policyStorageKey(policyId), candidate ? JSON.stringify(candidate) : null)
  }

  const clearSelectedPolicy = async () => {
    if (chatSessionId) {
      await apiFetch<ChatSessionResponse>(`/api/v1/chat/sessions/${chatSessionId}/policy`, {
        method: 'DELETE',
      })
    }
    persistSessionPolicy(null)
  }

  const askChatbot = async (query: string) => {
    if (!policyId && isRecommendationRequest(query)) {
      try {
        await clearSelectedPolicy()
      } catch {
        // 추천 기능 자체는 세션 정리 실패와 무관하게 실행한다.
        persistSessionPolicy(null)
      }
      await askRecommendations(query)
      return
    }

    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: policyId
        ? '선택한 공고문에서 근거를 찾고 있어요.'
        : sessionPolicy
          ? '선택한 공고문과 이전 대화 문맥을 확인하고 있어요.'
          : '전체 정책 문서에서 관련 근거를 찾고 있어요.',
      pending: true,
    })

    try {
      const path = policyId
        ? `/api/v1/chat/ask?policy_id=${encodeURIComponent(policyId)}`
        : '/api/v1/chat/ask'
      const data = await apiFetch<ChatAnswerResponse>(path, {
        method: 'POST',
        json: {
          query,
          limit: 6,
          ...(chatSessionId ? { session_id: chatSessionId } : {}),
          ...(!policyId && sessionPolicy?.policy_id ? { selected_policy_id: sessionPolicy.policy_id } : {}),
        },
      })
      persistSessionId(data.session_id)

      if (!policyId && data.active_policy_id === null) {
        persistSessionPolicy(null)
      }
      replace(pendingId, {
        role: 'bot',
        text: data.answer || '공고문에서 답변 근거를 찾지 못했어요. 질문을 조금 더 구체적으로 입력해 주세요.',
        sources: data.response_mode === 'policy_selection' ? [] : data.sources,
        candidates: data.candidates,
      })
    } catch (error) {
      const detail = error instanceof Error ? error.message : ''
      if (detail.includes('대화 세션')) {
        setChatSessionId(null)
        writeStorage(sessionStorageKey(policyId), null)
        persistSessionPolicy(null)
      }
      replace(pendingId, {
        role: 'bot',
        text: detail.includes('로그인')
          ? detail
          : '정책 상담 API를 호출하지 못했어요. 잠시 후 다시 시도해 주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const askRecommendations = async (sourceQuery = '맞춤 정책 추천해줘') => {
    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: '사장님 프로필을 기준으로 맞춤 정책을 찾고 있어요.',
      pending: true,
    })

    try {
      const params = new URLSearchParams({
        limit: '3',
        source_query: sourceQuery,
      })
      if (chatSessionId) {
        params.set('chat_session_id', chatSessionId)
      }
      const data = await apiFetch<RecommendationPreviewResponse>(`/api/v1/recommend/preview?${params.toString()}`, {
        method: 'POST',
        json: buildRecommendationRequest(profile),
      })
      if (data.chat_session_id) {
        persistSessionId(data.chat_session_id)
      }
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
          ? `사장님 조건과 가까운 정책 ${policies.length}건을 찾았어요. 각 정책을 눌러 상세 화면에서 지원 대상이나 서류를 이어서 물어볼 수 있어요.${data.profile_warnings?.[0] ? `\n\n입력 정보 확인: ${data.profile_warnings[0]}` : ''}`
          : '지금 프로필 기준으로 바로 추천할 정책을 찾지 못했어요. 업종, 지역, 매출 정보를 조금 더 채워보면 추천 정확도가 올라가요.',
        policies,
      })
    } catch {
      replace(pendingId, {
        role: 'bot',
        text: '맞춤 추천 API를 호출하지 못했어요. 잠시 후 다시 시도해 주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const selectCandidate = async (candidate: ChatPolicyCandidate) => {
    if (!chatSessionId || selectingPolicyId) return
    setSelectingPolicyId(candidate.policy_id)
    try {
      const data = await apiFetch<ChatSessionResponse>(`/api/v1/chat/sessions/${chatSessionId}/policy`, {
        method: 'POST',
        json: { policy_id: candidate.policy_id },
      })
      persistSessionId(data.session_id)
      persistSessionPolicy(candidate)
      push({
        role: 'bot',
        text: `‘${candidate.title}’ 공고를 기준으로 계속 상담할게요. 이제 “서류는?”, “마감은?”처럼 짧게 이어서 물어봐도 됩니다.`,
      })
    } catch {
      push({
        role: 'bot',
        text: '선택한 공고 문맥을 저장하지 못했어요. 공고를 다시 선택해 주세요.',
      })
    } finally {
      setSelectingPolicyId(null)
    }
  }

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    push({ role: 'user', text: trimmed })
    setInput('')
    void askChatbot(trimmed)
  }

  const handleToggleSave = async (targetPolicyId: string) => {
    setPendingSave(targetPolicyId)
    try {
      await toggle(targetPolicyId)
    } finally {
      setPendingSave(null)
    }
  }

  const isPolicyContextActive = Boolean(policyId || sessionPolicy)

  return (
    <div className="flex h-full flex-col">
      <TopBar />

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {policyId && (
          <div className="rounded-2xl bg-primary p-4 text-white shadow-card">
            <p className="text-sm font-semibold">선택한 정책 공고 상담을 이어가고 있어요.</p>
            <p className="mt-1 text-xs text-white/70">이 공고문만 기준으로 답변합니다.</p>
            <button
              onClick={() => navigate(`/policy/${policyId}`)}
              className="mt-3 rounded-xl bg-surface px-3 py-2 text-xs font-bold text-ink"
            >
              정책 상세 다시 보기
            </button>
          </div>
        )}

        {!policyId && sessionPolicy && (
          <div className="flex items-start justify-between gap-3 rounded-2xl bg-brand-dark p-4 text-white shadow-card">
            <div>
              <p className="text-xs text-white/70">현재 상담 중인 정책</p>
              <p className="mt-1 text-sm font-semibold">{sessionPolicy.title}</p>
              <p className="mt-1 text-xs text-white/70">짧은 후속 질문은 이 공고문 기준으로 답변해요.</p>
            </div>
            <button
              type="button"
              onClick={() => void clearSelectedPolicy()}
              className="rounded-xl bg-white/15 p-2 text-white"
              aria-label="전체 정책 검색으로 전환"
              title="전체 정책 검색으로 전환"
            >
              <X size={17} />
            </button>
          </div>
        )}

        {messages.map((message) =>
          message.role === 'bot' ? (
            <BotBubble
              key={message.id}
              message={message}
              navigate={navigate}
              has={has}
              onToggleSave={handleToggleSave}
              pendingSave={pendingSave}
              onSelectCandidate={selectCandidate}
              selectingPolicyId={selectingPolicyId}
              detailMode={Boolean(policyId)}
            />
          ) : (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[78%] whitespace-pre-line rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-[15px] leading-relaxed text-white">
                {message.text}
              </p>
            </div>
          ),
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          {(isPolicyContextActive ? DETAIL_QUICK : QUICK).map((question) => (
            <button
              key={question}
              onClick={() => send(question)}
              disabled={sending}
              className="rounded-full border border-brand-light/40 bg-white px-4 py-2 text-sm font-medium text-ink active:bg-line/50"
            >
              {question}
            </button>
          ))}
        </div>
      </div>

      {/* 입력창 */}
      <div className="border-t border-line bg-cream px-4 py-3">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2 rounded-full border border-brand-light/40 bg-white py-1.5 pl-2 pr-1.5"
        >
          <button type="button" className="p-2 text-subtle" aria-label="첨부 기능 준비 중">
            <Plus size={22} />
          </button>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="메시지를 입력하세요..."
            className="flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-subtle"
          />
          <button
            type="submit"
            disabled={sending}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-white transition-colors active:bg-primary-hover disabled:bg-line disabled:text-subtle"
          >
            {sending ? <LoaderCircle size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  )
}

function BotBubble({
  message,
  navigate,
  has,
  onToggleSave,
  pendingSave,
  onSelectCandidate,
  selectingPolicyId,
  detailMode,
}: {
  message: Message
  navigate: ReturnType<typeof useNavigate>
  has: (id: string) => boolean
  onToggleSave: (policyId: string) => void
  pendingSave: string | null
  onSelectCandidate: (candidate: ChatPolicyCandidate) => void
  selectingPolicyId: string | null
  detailMode: boolean
}) {
  const visibleSources = message.sources
    ? (detailMode ? uniqueSourcesByDocument(message.sources) : uniqueSourcesByPolicy(message.sources)).slice(0, 3)
    : []

  return (
    <div className="flex items-start gap-2">
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-ink">
        <Bot size={20} className="text-muted" />
      </span>
      <div className="max-w-[82%] space-y-2">
        {message.text && (
          <p className="whitespace-pre-line rounded-2xl rounded-tl-md bg-white px-4 py-3 text-[15px] leading-relaxed text-ink shadow-card">
            <span className="flex items-start gap-2">
              {message.pending && <LoaderCircle size={17} className="mt-0.5 flex-shrink-0 animate-spin" />}
              <span>{message.text}</span>
            </span>
          </p>
        )}

        {message.candidates && message.candidates.length > 0 && (
          <div className="space-y-2 rounded-2xl border border-brand-light/30 bg-white p-3 shadow-card">
            {message.candidates.map((candidate) => (
              <div key={candidate.policy_id} className="rounded-xl bg-cream px-3 py-3">
                <p className="text-sm font-bold text-brand-dark">{candidate.title}</p>
                {candidate.support_type && <p className="mt-1 text-xs text-brand-dark/60">{candidate.support_type}</p>}
                {candidate.summary && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-brand-dark/60">{candidate.summary}</p>}
                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => onSelectCandidate(candidate)}
                    disabled={selectingPolicyId !== null}
                    className="rounded-lg bg-brand-dark px-3 py-2 text-xs font-bold text-white disabled:opacity-50"
                  >
                    {selectingPolicyId === candidate.policy_id ? '선택 중...' : '이 정책으로 계속 상담'}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/policy/${candidate.policy_id}`)}
                    className="flex items-center gap-1 text-xs font-bold text-brand"
                  >
                    상세 보기 <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {visibleSources.length > 0 && (
          <div className="rounded-2xl border border-brand-light/30 bg-white p-3 shadow-card">
            <p className="text-xs font-bold text-muted">답변 근거</p>
            <div className="mt-2 space-y-2">
              {visibleSources.map((source) => (
                <div key={source.chunk_id} className="rounded-xl bg-cream px-3 py-2.5">
                  <p className="text-xs font-semibold text-muted">
                    {source.policy_title || source.document_title || '공고문'}
                  </p>
                  <p className="mt-0.5 text-[11px] font-medium text-subtle">
                    {documentTypeLabel(source.document_type)}
                    {source.source_ref ? ` · ${source.source_ref}` : ''}
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

        {message.policies && message.policies.length > 0 && (
          <div className="space-y-3">
            {message.policies.map((policy) => (
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
        {message.time && <p className="pl-1 text-xs text-subtle">{message.time}</p>}
      </div>
    </div>
  )
}

function isRecommendationRequest(text: string) {
  const normalized = text.trim().toLowerCase()
  const recommendationSignals = ['추천', '맞춤', '나에게', '내게', '내가 받을', '받을 수', '찾아줘', '찾아 줘']
  const nonPolicySignals = ['맛집', '음식', '메뉴', '노래', '영화', '드라마', '여행', '옷', '코디', '머리', '단발', '미용실']
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
  if (nonPolicySignals.some((keyword) => normalized.includes(keyword))) return false

  // 로그인 사용자의 메인 채팅에서 "추천해줘"만 입력해도 프로필 기반 추천으로 연결한다.
  // 다만 정책과 무관한 추천 키워드는 위에서 먼저 제외한다.
  return recommendationSignals.some((keyword) => normalized.includes(keyword))
    && (policyDomainSignals.some((keyword) => normalized.includes(keyword)) || normalized.length <= 8)
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
