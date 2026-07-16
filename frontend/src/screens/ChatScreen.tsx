import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ChevronDown, History, LoaderCircle, MessageSquarePlus, Send, X } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import PolicyCard, { type PolicyCardData } from '../components/PolicyCard'
import ChatHistoryDrawer from '../components/ChatHistoryDrawer'
import TopBar from '../components/TopBar'
import assistantBotIcon from '../assets/sobok-assistant-bot.png'
import { Panel } from '../components/ui'
import { ApiError, apiFetch, apiFetchStream } from '../lib/api'
import { buildRecommendationRequest } from '../lib/recommend'
import { useProfile, useSavedPolicies } from '../lib/storage'
import type {
  ChatAnswerResponse,
  ChatChunkSource,
  ChatHistoryDetailResponse,
  ChatHistoryListResponse,
  ChatHistoryPolicy,
  ChatHistorySession,
  ChatPolicyCandidate,
  ChatSessionResponse,
  RecommendationPreviewResponse,
} from '../types'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  sources?: ChatChunkSource[]
  candidates?: ChatPolicyCandidate[]
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

function historyPolicyToCandidate(policy?: ChatHistoryPolicy | null): ChatPolicyCandidate | null {
  if (!policy) return null
  return {
    policy_id: policy.policy_id,
    title: policy.title,
    summary: policy.summary,
    support_type: policy.support_type,
    apply_end: policy.apply_end,
    score: 0,
    source_count: 0,
  }
}

function historyCandidateToChatCandidate(value: Record<string, unknown>): ChatPolicyCandidate | null {
  const policyId = typeof value.policy_id === 'string' ? value.policy_id : null
  const title = typeof value.title === 'string' ? value.title : null
  if (!policyId || !title) return null
  return {
    policy_id: policyId,
    title,
    summary: typeof value.summary === 'string' ? value.summary : null,
    support_type: typeof value.support_type === 'string' ? value.support_type : null,
    apply_end: typeof value.apply_end === 'string' ? value.apply_end : null,
    score: typeof value.score === 'number' ? value.score : 0,
    source_count: typeof value.source_count === 'number' ? value.source_count : 0,
  }
}

function historyCandidateToPolicy(value: Record<string, unknown>): PolicyCardData | null {
  const policyId = typeof value.policy_id === 'string' ? value.policy_id : null
  const title = typeof value.title === 'string' ? value.title : null
  if (!policyId || !title) return null

  const eligibilityStatus =
    value.eligibility_status === 'eligible' || value.eligibility_status === 'needs_review'
      ? value.eligibility_status
      : undefined
  const preferenceMatch =
    value.preference_match === 'exact' ||
    value.preference_match === 'partial' ||
    value.preference_match === 'none' ||
    value.preference_match === 'not_requested'
      ? value.preference_match
      : undefined
  const matchStatus =
    value.match_status === 'eligible' ||
    value.match_status === 'needs_review' ||
    value.match_status === 'near_match'
      ? value.match_status
      : undefined
  const stringList = (candidate: unknown) =>
    Array.isArray(candidate) ? candidate.filter((item): item is string => typeof item === 'string') : []

  return {
    policy_id: policyId,
    title,
    summary: typeof value.summary === 'string' ? value.summary : null,
    support_type: typeof value.support_type === 'string' ? value.support_type : null,
    apply_end: typeof value.apply_end === 'string' ? value.apply_end : null,
    rank_score: typeof value.rank_score === 'number' ? value.rank_score : undefined,
    eligibility_status: eligibilityStatus,
    preference_match: preferenceMatch,
    match_status: matchStatus,
    reasons: stringList(value.reasons),
    warnings: stringList(value.warnings),
    unmet_conditions: stringList(value.unmet_conditions),
  }
}

function restoreHistoryMessages(detail: ChatHistoryDetailResponse): Message[] {
  return detail.messages.map((message, index) => {
    if (message.role === 'user') {
      return {
        id: index + 1,
        role: 'user' as const,
        text: message.content,
      }
    }

    const candidates = message.candidates
      .map(historyCandidateToChatCandidate)
      .filter((candidate): candidate is ChatPolicyCandidate => candidate !== null)
    const policies = message.response_mode === 'recommendation'
      ? message.candidates
          .map(historyCandidateToPolicy)
          .filter((policy): policy is PolicyCardData => policy !== null)
      : []

    return {
      id: index + 1,
      role: 'bot' as const,
      text: message.content,
      sources: message.sources,
      candidates: policies.length > 0 ? undefined : candidates,
      policies: policies.length > 0 ? policies : undefined,
    }
  })
}

interface ChatStreamMeta {
  session_id: string
  response_mode?: ChatAnswerResponse['response_mode']
  sources?: ChatChunkSource[]
  candidates?: ChatPolicyCandidate[]
  active_policy_id?: string | null
}

interface ChatStreamHandlers {
  onMeta: (meta: ChatStreamMeta) => void
  onToken: (text: string) => void
  onDone: (data: { answer: string }) => void
}

async function consumeChatStream(response: Response, handlers: ChatStreamHandlers) {
  if (!response.body) throw new Error('AI 스트리밍 응답을 읽을 수 없습니다.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const consumeEvent = (block: string) => {
    let eventName = 'message'
    let data = ''
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) return

    const payload = JSON.parse(data) as Record<string, unknown>
    if (eventName === 'meta') {
      handlers.onMeta(payload as unknown as ChatStreamMeta)
    } else if (eventName === 'token' && typeof payload.text === 'string') {
      handlers.onToken(payload.text)
    } else if (eventName === 'done') {
      handlers.onDone({ answer: typeof payload.answer === 'string' ? payload.answer : '' })
    } else if (eventName === 'error') {
      throw new Error(
        typeof payload.message === 'string'
          ? payload.message
          : 'AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.',
      )
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    blocks.forEach(consumeEvent)
    if (done) break
  }

  if (buffer.trim()) consumeEvent(buffer)
}

export default function ChatScreen() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const policyId = searchParams.get('policyId')
  const { profile } = useProfile()
  const { has, toggle } = useSavedPolicies()
  const [messages, setMessages] = useState<Message[]>(() => initialMessagesFor(policyId))
  const [chatSessionId, setChatSessionId] = useState<string | null>(() => readStorage(sessionStorageKey(policyId)))
  const [sessionPolicy, setSessionPolicy] = useState<ChatPolicyCandidate | null>(() => readStoredCandidate(policyId))
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [selectingPolicyId, setSelectingPolicyId] = useState<string | null>(null)
  const [pendingSave, setPendingSave] = useState<string | null>(null)
  const [policyContext, setPolicyContext] = useState<PolicyContext | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historySessions, setHistorySessions] = useState<ChatHistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyRestoring, setHistoryRestoring] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [selectingHistoryId, setSelectingHistoryId] = useState<string | null>(null)
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null)
  const nextId = useRef(2)
  const messageScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const container = messageScrollRef.current
      if (!container) return

      const latestMessage = messages[messages.length - 1]
      if (latestMessage?.role === 'bot') {
        const target = container.querySelector<HTMLElement>(
          `[data-message-id="${latestMessage.id}"]`,
        )
        if (target) {
          const targetTop =
            target.getBoundingClientRect().top -
            container.getBoundingClientRect().top +
            container.scrollTop
          container.scrollTo({ top: Math.max(0, targetTop - 8), behavior: 'smooth' })
          return
        }
      }

      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    })

    return () => window.cancelAnimationFrame(frame)
  }, [messages])

  useEffect(() => {
    let ignore = false
    const storedSessionId = readStorage(sessionStorageKey(policyId))
    const storedPolicy = readStoredCandidate(policyId)

    setMessages(initialMessagesFor(policyId))
    setChatSessionId(storedSessionId)
    setSessionPolicy(storedPolicy)
    setInput('')
    setSending(false)
    setSelectingPolicyId(null)
    nextId.current = 2

    if (!storedSessionId) {
      setHistoryRestoring(false)
      return () => {
        ignore = true
      }
    }

    setHistoryRestoring(true)
    apiFetch<ChatHistoryDetailResponse>(`/api/v1/chat/sessions/${storedSessionId}`)
      .then((detail) => {
        if (ignore) return
        const restoredMessages = restoreHistoryMessages(detail)
        const activePolicy = historyPolicyToCandidate(detail.session.active_policy)
        setMessages(restoredMessages.length > 0 ? restoredMessages : initialMessagesFor(policyId))
        setChatSessionId(detail.session.session_id)
        if (!policyId) {
          setSessionPolicy(activePolicy)
          writeStorage(policyStorageKey(null), activePolicy ? JSON.stringify(activePolicy) : null)
        }
        nextId.current = Math.max(2, restoredMessages.length + 1)
      })
      .catch((error) => {
        if (ignore) return
        if (error instanceof ApiError && error.status === 404) {
          writeStorage(sessionStorageKey(policyId), null)
          writeStorage(policyStorageKey(policyId), null)
          setChatSessionId(null)
          setSessionPolicy(null)
        }
      })
      .finally(() => {
        if (!ignore) setHistoryRestoring(false)
      })

    return () => {
      ignore = true
    }
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

  const persistSessionId = (sessionId: string) => {
    setChatSessionId(sessionId)
    writeStorage(sessionStorageKey(policyId), sessionId)
  }

  const persistSessionPolicy = (candidate: ChatPolicyCandidate | null) => {
    setSessionPolicy(candidate)
    writeStorage(policyStorageKey(policyId), candidate ? JSON.stringify(candidate) : null)
  }

  const openChatHistory = () => {
    setHistoryOpen(true)
    setHistoryLoading(true)
    setHistoryError(null)
    void apiFetch<ChatHistoryListResponse>('/api/v1/chat/sessions?limit=100')
      .then((data) => setHistorySessions(data.items))
      .catch((error) => {
        setHistoryError(error instanceof Error ? error.message : '잠시 후 다시 시도해 주세요.')
      })
      .finally(() => setHistoryLoading(false))
  }

  const startNewConversation = () => {
    setMessages(initialMessagesFor(policyId))
    setChatSessionId(null)
    setSessionPolicy(null)
    setInput('')
    setSending(false)
    setSelectingPolicyId(null)
    writeStorage(sessionStorageKey(policyId), null)
    writeStorage(policyStorageKey(policyId), null)
    nextId.current = 2
    setHistoryOpen(false)
  }

  const applyHistoryDetail = (detail: ChatHistoryDetailResponse) => {
    const restoredMessages = restoreHistoryMessages(detail)
    const activePolicy = historyPolicyToCandidate(detail.session.active_policy)

    writeStorage(sessionStorageKey(null), detail.session.session_id)
    writeStorage(policyStorageKey(null), activePolicy ? JSON.stringify(activePolicy) : null)

    if (policyId) {
      setHistoryOpen(false)
      navigate('/chat', { replace: true })
      return
    }

    setMessages(restoredMessages.length > 0 ? restoredMessages : initialMessages)
    setChatSessionId(detail.session.session_id)
    setSessionPolicy(activePolicy)
    nextId.current = Math.max(2, restoredMessages.length + 1)
    setHistoryOpen(false)
  }

  const selectHistorySession = async (session: ChatHistorySession) => {
    if (session.session_id === chatSessionId && !policyId) {
      setHistoryOpen(false)
      return
    }
    setSelectingHistoryId(session.session_id)
    setHistoryError(null)
    try {
      const detail = await apiFetch<ChatHistoryDetailResponse>(
        `/api/v1/chat/sessions/${session.session_id}`,
      )
      applyHistoryDetail(detail)
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '대화를 다시 불러오지 못했어요.')
    } finally {
      setSelectingHistoryId(null)
    }
  }

  const deleteHistorySession = async (session: ChatHistorySession) => {
    const confirmed = window.confirm(`‘${session.title}’ 대화를 삭제할까요? 삭제한 대화는 복구할 수 없습니다.`)
    if (!confirmed) return

    setDeletingHistoryId(session.session_id)
    setHistoryError(null)
    try {
      await apiFetch<void>(`/api/v1/chat/sessions/${session.session_id}`, { method: 'DELETE' })
      setHistorySessions((previous) => previous.filter((item) => item.session_id !== session.session_id))
      if (chatSessionId === session.session_id) {
        startNewConversation()
      }
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '대화를 삭제하지 못했어요.')
    } finally {
      setDeletingHistoryId(null)
    }
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
        ? '선택한 공고문에서 답변에 필요한 내용을 확인하고 있습니다.'
        : sessionPolicy
          ? '선택한 공고문과 이전 대화를 기준으로 내용을 확인하고 있습니다.'
          : '정책 문서에서 관련 내용을 확인하고 있습니다.',
      pending: true,
    })

    let streamedText = ''
    let streamSources: ChatChunkSource[] = []
    let streamCandidates: ChatPolicyCandidate[] = []
    let streamCompleted = false

    try {
      const path = policyId
        ? `/api/v1/chat/ask/stream?policy_id=${encodeURIComponent(policyId)}`
        : '/api/v1/chat/ask/stream'
      const response = await apiFetchStream(path, {
        method: 'POST',
        json: {
          query,
          limit: 6,
          ...(chatSessionId ? { session_id: chatSessionId } : {}),
          ...(!policyId && sessionPolicy?.policy_id ? { selected_policy_id: sessionPolicy.policy_id } : {}),
        },
      })

      await consumeChatStream(response, {
        onMeta: (meta) => {
          persistSessionId(meta.session_id)
          streamSources = meta.response_mode === 'policy_selection' ? [] : meta.sources || []
          streamCandidates = meta.candidates || []
          if (!policyId && meta.active_policy_id === null) {
            persistSessionPolicy(null)
          }
        },
        onToken: (text) => {
          streamedText += text
          replace(pendingId, {
            role: 'bot',
            text: streamedText,
            sources: streamSources,
            candidates: streamCandidates,
            pending: true,
          })
        },
        onDone: ({ answer }) => {
          streamCompleted = true
          streamedText = answer || streamedText
          replace(pendingId, {
            role: 'bot',
            text: streamedText || '공고문에서 답변 근거를 찾지 못했어요. 질문을 조금 더 구체적으로 입력해 주세요.',
            sources: streamSources,
            candidates: streamCandidates,
          })
        },
      })
      if (!streamCompleted) throw new Error('AI 답변 스트림이 정상적으로 끝나지 않았습니다.')
    } catch (error) {
      const detail = error instanceof Error ? error.message : ''
      if (detail.includes('대화 세션')) {
        setChatSessionId(null)
        writeStorage(sessionStorageKey(policyId), null)
        persistSessionPolicy(null)
      }
      replace(pendingId, {
        role: 'bot',
        text: streamedText
          ? `${streamedText}\n\n${detail || 'AI 답변을 끝까지 불러오지 못했습니다.'}`
          : detail || '정책 내용을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
        sources: streamSources,
        candidates: streamCandidates,
      })
    } finally {
      setSending(false)
    }
  }

  const askRecommendations = async (sourceQuery = '맞춤 정책 추천해줘') => {
    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: '입력한 사업장 정보를 기준으로 맞춤 정책을 확인하고 있습니다.',
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
          ? `입력한 조건과 가까운 정책 ${policies.length}건을 확인했습니다. 정책을 누르면 지원 대상과 필요 서류를 이어서 확인할 수 있습니다.${data.profile_warnings?.[0] ? `\n\n입력 정보 확인: ${data.profile_warnings[0]}` : ''}`
          : '현재 입력 정보로 추천할 정책을 찾지 못했습니다. 마이페이지에서 업종, 지역, 매출 정보를 확인해 주세요.',
        policies,
      })
    } catch (error) {
      replace(pendingId, {
        role: 'bot',
        text:
          error instanceof Error
            ? error.message
            : '맞춤 정책을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
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
        text: `‘${candidate.title}’ 공고가 상담 기준으로 선택되었습니다. 이후 질문은 이 공고문을 기준으로 확인합니다.`,
      })
    } catch {
      push({
        role: 'bot',
        text: '선택한 공고를 상담 기준으로 저장하지 못했습니다. 다시 선택해 주세요.',
      })
    } finally {
      setSelectingPolicyId(null)
    }
  }

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending || historyRestoring) return
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

  const lastMessage = messages[messages.length - 1]
  const showQuickQuestions = !sending && lastMessage?.role === 'bot' && !lastMessage.pending
  const isPolicyContextActive = Boolean(policyId || sessionPolicy)

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <h1 className="sr-only">정책 도우미</h1>

      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-3">
        <button
          type="button"
          onClick={openChatHistory}
          disabled={sending}
          className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3.5 text-sm font-bold text-ink shadow-card outline-none transition-colors active:bg-line/30 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-primary/20"
        >
          <History size={17} className="text-brand" />
          대화 기록
        </button>
        <button
          type="button"
          onClick={startNewConversation}
          disabled={sending || historyRestoring}
          className="flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-bold text-primary outline-none transition-colors active:bg-primary-soft disabled:text-faint focus-visible:ring-2 focus-visible:ring-primary/20"
        >
          <MessageSquarePlus size={17} />
          새 대화
        </button>
      </div>

      <ChatHistoryDrawer
        open={historyOpen}
        sessions={historySessions}
        currentSessionId={chatSessionId}
        loading={historyLoading}
        error={historyError}
        selectingSessionId={selectingHistoryId}
        deletingSessionId={deletingHistoryId}
        onClose={() => setHistoryOpen(false)}
        onNewChat={startNewConversation}
        onSelect={(session) => void selectHistorySession(session)}
        onDelete={(session) => void deleteHistorySession(session)}
      />

      <div
        ref={messageScrollRef}
        className="no-scrollbar min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 pb-5 pt-1"
      >
        {historyRestoring && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs font-medium text-muted">
            <LoaderCircle size={15} className="animate-spin text-primary" />
            이전 대화를 불러오는 중이에요.
          </div>
        )}
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

        {!policyId && sessionPolicy && (
          <div className="flex items-start justify-between gap-3 rounded-2xl bg-brand-dark p-4 text-white shadow-card">
            <div>
              <p className="text-xs text-white/70">현재 상담 중인 정책</p>
              <p className="mt-1 text-sm font-semibold">{sessionPolicy.title}</p>
              <p className="mt-1 text-xs text-white/70">후속 질문은 이 공고문을 기준으로 답변합니다.</p>
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
              <p className="max-w-[82%] whitespace-pre-line rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-sm font-semibold leading-relaxed text-white shadow-card">
                {message.text}
              </p>
            </div>
          ),
        )}

        {showQuickQuestions && (
          <section
            className="surface-panel ml-[60px] overflow-hidden shadow-card"
            aria-label="추천 질문"
          >
            <div className="border-b border-line bg-primary-soft/60 px-4 py-2.5">
              <p className="text-xs font-bold text-primary">이어서 물어보세요</p>
            </div>
            <div className="divide-y divide-line">
              {(isPolicyContextActive ? DETAIL_QUICK : QUICK).map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => send(question)}
                  className="flex min-h-12 w-full items-center justify-between gap-3 px-4 py-3 text-left text-[13px] font-semibold leading-snug text-ink outline-none transition-colors active:bg-line/40 focus-visible:bg-primary-soft/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/20"
                >
                  <span>{question}</span>
                  <ArrowRight size={16} strokeWidth={1.8} className="shrink-0 text-brand-light" />
                </button>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="border-t border-line bg-cream px-3 pb-3 pt-2">
        <p className="mb-1.5 text-center text-[11px] leading-relaxed text-subtle">
          답변은 공고문을 자동으로 정리한 참고 내용입니다.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            send(input)
          }}
          className="flex h-14 items-center rounded-full border border-line bg-surface p-1.5 pl-5 shadow-card transition-colors focus-within:border-primary/40"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={historyRestoring}
            placeholder="확인할 내용을 입력하세요"
            aria-label="정책 질문"
            className="min-w-0 flex-1 bg-transparent pr-2 text-[15px] text-ink outline-none placeholder:text-subtle"
          />
          <button
            type="submit"
            disabled={sending || historyRestoring || !input.trim()}
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
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  const uniqueSources = message.sources
    ? detailMode
      ? uniqueSourcesByDocument(message.sources)
      : uniqueSourcesByPolicy(message.sources)
    : []
  const visibleSources = uniqueSources.slice(0, 3)
  const displayText = cleanChatDisplayText(message.text || '')

  return (
    <div className="space-y-2" data-message-id={message.id}>
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
            {message.pending && (
              <LoaderCircle size={17} className="mr-2 inline-block animate-spin text-muted" />
            )}
            <p className="inline whitespace-pre-line text-sm leading-[1.75] text-ink">{displayText}</p>
          </div>
        </div>
      )}

      {message.candidates && message.candidates.length > 0 && (
        <div className="ml-[60px] overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
          {message.candidates.map((candidate, index) => (
            <article
              key={candidate.policy_id}
              className={`p-4 ${index > 0 ? 'border-t border-line' : ''}`}
            >
              <p className="text-sm font-bold leading-snug text-ink">{candidate.title}</p>
              {candidate.support_type && (
                <p className="mt-1 text-xs font-medium text-brand">{candidate.support_type}</p>
              )}
              {candidate.summary && (
                <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">
                  {candidate.summary}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onSelectCandidate(candidate)}
                  disabled={selectingPolicyId !== null}
                  className="flex min-h-10 items-center rounded-xl bg-primary px-3 text-xs font-bold text-white outline-none transition-colors active:bg-primary-hover disabled:bg-line disabled:text-subtle focus-visible:ring-2 focus-visible:ring-primary/25"
                >
                  {selectingPolicyId === candidate.policy_id ? '선택 중' : '이 정책으로 질문하기'}
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/policy/${candidate.policy_id}`)}
                  className="flex min-h-10 items-center gap-1 rounded-xl border border-line bg-surface px-3 text-xs font-bold text-brand outline-none transition-colors active:bg-line/40 focus-visible:ring-2 focus-visible:ring-primary/20"
                >
                  상세 보기 <ArrowRight size={13} />
                </button>
              </div>
            </article>
          ))}
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

      {message.policies && message.policies.length > 0 && (
        <Panel divided className="ml-[60px]">
          {message.policies.map((policy) => (
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
  const recommendationSignals = ['추천', '맞춤', '나에게', '내게', '내가 받을', '받을 수', '찾아줘', '찾아 줘']
  const nonPolicySignals = ['맛집', '음식', '메뉴', '노래', '영화', '드라마', '여행', '옷', '코디', '머리', '단발', '미용실']
  const policyDomainSignals = [
    '정책',
    '공고',
    '복지',
    '지원',
    '지원금',
    '현금',
    '현금성',
    '지급',
    '장려금',
    '급여',
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
