import { useRef, useState } from 'react'
import { Bookmark, Bot, CalendarDays, Plus, Send } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { benefits, getBenefit } from '../data/benefits'
import { useBookmarks } from '../lib/storage'

interface Message {
  id: number
  role: 'bot' | 'user'
  text?: string
  benefitId?: string
  time?: string
}

const QUICK = ['내 업종 지원금 찾아줘', '공고문 요약해줘', '세무 일정 알려줘']

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
  const { has, toggle } = useBookmarks()
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const nextId = useRef(2)

  const push = (m: Omit<Message, 'id'>) => {
    const id = nextId.current++
    setMessages((prev) => [...prev, { ...m, id }])
    return id
  }

  const send = (text: string) => {
    const t = text.trim()
    if (!t) return
    push({ role: 'user', text: t })
    setInput('')
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
          {QUICK.map((q) => (
            <button
              key={q}
              onClick={() => send(q)}
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
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white active:scale-95"
          >
            <Send size={18} />
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
            {m.text}
          </p>
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
