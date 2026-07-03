import { Bookmark, CalendarDays, ChevronLeft, MapPin, Tag } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { getBenefit } from '../data/benefits'
import { ddayLabel, statusMeta } from '../lib/format'
import { useBookmarks } from '../lib/storage'

export default function BenefitDetailScreen() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { has, toggle } = useBookmarks()
  const benefit = id ? getBenefit(id) : undefined

  if (!benefit) {
    return (
      <div className="app-frame flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-cream">
        <p className="text-brand-dark/60">혜택 정보를 찾을 수 없어요.</p>
        <button
          onClick={() => navigate('/')}
          className="rounded-xl bg-brand-dark px-5 py-2.5 text-white"
        >
          홈으로
        </button>
      </div>
    )
  }

  const meta = statusMeta[benefit.status]

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 flex items-center justify-between bg-cream/95 px-4 py-4 backdrop-blur">
        <button onClick={() => navigate(-1)} className="p-1 text-brand-dark active:opacity-60">
          <ChevronLeft size={26} />
        </button>
        <h1 className="text-lg font-semibold text-brand-dark">혜택 상세</h1>
        <button onClick={() => toggle(benefit.id)} className="p-1">
          <Bookmark
            size={24}
            className={has(benefit.id) ? 'fill-brand text-brand' : 'text-brand-dark/40'}
          />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-5 pb-28">
        <div className="flex items-center gap-2">
          <span className={`rounded-lg px-2.5 py-1 text-sm font-bold ${meta.iconBg} ${meta.text}`}>
            {meta.label}
          </span>
          <span className="rounded-lg bg-brand-dark/5 px-2.5 py-1 text-sm font-bold text-brand-dark/70">
            {ddayLabel(benefit.dueDate)}
          </span>
        </div>

        <h2 className="mt-4 text-2xl font-bold leading-snug text-brand-dark">
          {benefit.title}
        </h2>

        {benefit.amount && (
          <div className="mt-4 inline-flex items-center gap-2 rounded-xl bg-green-100 px-4 py-2">
            <span className="text-lg font-bold text-status-green">🎁 {benefit.amount}</span>
          </div>
        )}

        <div className="mt-6 space-y-3 rounded-2xl bg-white p-5 shadow-card">
          <InfoLine icon={Tag} label="분야" value={benefit.category} />
          <InfoLine icon={MapPin} label="지역" value={benefit.region ?? '전국'} />
          <InfoLine
            icon={CalendarDays}
            label="기간"
            value={
              benefit.startDate
                ? `${benefit.startDate.replaceAll('-', '.')} ~ ${benefit.endDate?.replaceAll('-', '.') ?? ''}`
                : `${benefit.dueDate.replaceAll('-', '.')} ${benefit.timeLabel ?? ''}`
            }
          />
        </div>

        <h3 className="mt-6 text-lg font-bold text-brand-dark">지원 내용</h3>
        <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed text-brand-dark/70">
          {benefit.content ?? benefit.summary}
        </p>
      </div>

      {/* 하단 고정 CTA */}
      <div className="absolute bottom-0 left-0 right-0 border-t border-black/5 bg-cream px-5 py-4">
        <button className="w-full rounded-2xl bg-brand-dark py-4 text-lg font-bold text-white active:scale-[0.99]">
          신청하러 가기
        </button>
      </div>
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
    <div className="flex items-center gap-3">
      <Icon size={18} className="text-brand" />
      <span className="w-12 text-sm text-brand-dark/50">{label}</span>
      <span className="text-[15px] font-semibold text-brand-dark">{value}</span>
    </div>
  )
}
