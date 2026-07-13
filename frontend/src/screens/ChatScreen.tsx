import { useRef, useState } from 'react'
import { Bookmark, Bot, CalendarDays, LoaderCircle, Plus, Send } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { benefits, getBenefit } from '../data/benefits'
import { apiFetch } from '../lib/api'
import { useBookmarks } from '../lib/storage'
import type { ChatAnswerResponse, ChatChunkSource } from '../types'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  benefitId?: string
  time?: string
  sources?: ChatChunkSource[]
  pending?: boolean
}

const QUICK = ['내 업종 지원금 찾아줘', '공고문 요약해줘', '세무 일정 알려줘']

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
  const { has, toggle } = useBookmarks()
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
  const nextId = useRef(2)

  const push = (m: Omit<Message, 'id'>) => {
    const id = nextId.current++
    setMessages((prev) => [...prev, { ...m, id }])
    return id
  }

  const replace = (id: number, next: Omit<Message, 'id'>) => {
    setMessages((prev) => prev.map((message) => (message.id === id ? { ...next, id } : message)))
  }

  const askSelectedPolicy = async (query: string) => {
    if (!policyId) return

    setSending(true)
    const pendingId = push({
      role: 'bot',
      text: '공고문에서 답변 근거를 찾고 있어요.',
      pending: true,
    })

    try {
      const data = await apiFetch<ChatAnswerResponse>(
        `/api/v1/chat/ask?policy_id=${encodeURIComponent(policyId)}`,
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
          : '공고 상담 API를 호출하지 못했어요. 잠시 후 다시 시도해주세요.',
      })
    } finally {
      setSending(false)
    }
  }

  const send = (text: string) => {
    const t = text.trim()
    if (!t || (policyId && sending)) return
    push({ role: 'user', text: t })
    setInput('')
    if (policyId) {
      void askSelectedPolicy(t)
      return
    }
    // 간단한 목업 응답: 업종/지원금 관련이면 정책 카드 추천
    setTimeout(() => {
      if (t.includes('지원금') || t.includes('업종') || t.includes('찾')) {
        push({ role: 'bot', text: '사장님 업종에 딱 맞는 지원금을 발견했어요!' })
        push({ role: 'bot', benefitId: 'hvac-2024' })
      } else if (t.includes('요약')) {
        push({
          role: 'bot',
          text: '최근 공고 중 사장님께 유리한 건을 요약해드릴게요. 아래 카드를 확인해보세요.',
        })
        push({ role: 'bot', benefitId: 'digital-2024' })
      } else if (t.includes('세무') || t.includes('일정')) {
        const tax = benefits.find((b) => b.category === '세무')
        push({ role: 'bot', text: '다가오는 세무 일정을 정리했어요.' })
        if (tax) push({ role: 'bot', benefitId: tax.id })
      } else {
        push({
          role: 'bot',
          text: '알겠습니다! 관련 정보를 찾아 정리해드릴게요. 조금만 기다려주세요 🙂',
        })
      }
    }, 350)
  }

  return (
    <div className="flex h-full flex-col">
      <TopBar />

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {policyId && (
          <div className="rounded-2xl bg-brand-dark p-4 text-white shadow-card">
            <p className="text-sm font-semibold">선택한 정책 상담을 이어갈 수 있어요.</p>
            <p className="mt-1 break-all text-xs text-white/70">policyId: {policyId}</p>
            <button
              onClick={() => navigate(`/policy/${policyId}`)}
              className="mt-3 rounded-xl bg-white px-3 py-2 text-xs font-bold text-brand-dark"
            >
              정책 상세 다시 보기
            </button>
          </div>
        )}

        {messages.map((m) =>
          m.role === 'bot' ? (
            <BotBubble key={m.id} m={m} navigate={navigate} has={has} toggle={toggle} />
          ) : (
            <div key={m.id} className="flex justify-end">
              <p className="max-w-[78%] whitespace-pre-line rounded-2xl rounded-tr-md bg-brand-dark px-4 py-3 text-[15px] leading-relaxed text-white">
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
              disabled={Boolean(policyId && sending)}
              className="rounded-full border border-brand-light/40 bg-white px-4 py-2 text-sm font-medium text-brand-dark/80 active:bg-black/5"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* 입력창 */}
      <div className="border-t border-black/5 bg-cream px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2 rounded-full border border-brand-light/40 bg-white py-1.5 pl-2 pr-1.5"
        >
          <button type="button" className="p-2 text-brand-dark/40">
            <Plus size={22} />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요..."
            className="flex-1 bg-transparent text-[15px] text-brand-dark outline-none placeholder:text-brand-dark/35"
          />
          <button
            type="submit"
            disabled={Boolean(policyId && sending)}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white active:scale-95 disabled:opacity-50"
          >
            {policyId && sending ? <LoaderCircle size={18} className="animate-spin" /> : <Send size={18} />}
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
  toggle,
}: {
  m: Message
  navigate: ReturnType<typeof useNavigate>
  has: (id: string) => boolean
  toggle: (id: string) => void
}) {
  const benefit = m.benefitId ? getBenefit(m.benefitId) : undefined
  return (
    <div className="flex items-start gap-2">
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-brand-dark">
        <Bot size={20} className="text-status-blue" />
      </span>
      <div className="max-w-[82%] space-y-2">
        {m.text && (
          <p className="whitespace-pre-line rounded-2xl rounded-tl-md bg-white px-4 py-3 text-[15px] leading-relaxed text-brand-dark shadow-card">
            <span className="flex items-start gap-2">
              {m.pending && <LoaderCircle size={17} className="mt-0.5 flex-shrink-0 animate-spin" />}
              <span>{m.text}</span>
            </span>
          </p>
        )}
        {m.sources && m.sources.length > 0 && (
          <div className="rounded-2xl border border-brand-light/30 bg-white p-3 shadow-card">
            <p className="text-xs font-bold text-brand-dark/70">답변 근거</p>
            <div className="mt-2 space-y-2">
              {m.sources.slice(0, 3).map((source) => (
                <div key={source.chunk_id} className="rounded-xl bg-cream px-3 py-2.5">
                  <p className="text-xs font-semibold text-brand-dark/70">
                    {source.document_title || source.document_type || '공고문'}
                  </p>
                  <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-brand-dark/55">
                    {source.chunk_text}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
        {benefit && (
          <div className="rounded-2xl bg-white p-4 shadow-card">
            <div className="flex items-start justify-between">
              {benefit.amount && (
                <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-bold text-status-green">
                  {benefit.amount}
                </span>
              )}
              <button onClick={() => toggle(benefit.id)} className="p-1">
                <Bookmark
                  size={20}
                  className={
                    has(benefit.id) ? 'fill-brand text-brand' : 'text-brand-dark/30'
                  }
                />
              </button>
            </div>
            <h4 className="mt-3 text-xl font-bold leading-snug text-brand-dark">
              {benefit.title}
            </h4>
            {benefit.startDate && (
              <p className="mt-3 flex items-center gap-1.5 text-sm text-brand-dark/60">
                <CalendarDays size={16} />
                {benefit.startDate.replaceAll('-', '.')} -{' '}
                {benefit.endDate?.slice(5).replaceAll('-', '.')}
              </p>
            )}
            <button
              onClick={() => navigate(`/benefit/${benefit.id}`)}
              className="mt-4 w-full rounded-xl bg-brand-dark py-3 text-base font-semibold text-white active:scale-[0.99]"
            >
              자세히 보기
            </button>
          </div>
        )}
        {m.time && <p className="pl-1 text-xs text-brand-dark/40">{m.time}</p>}
      </div>
    </div>
  )
}
