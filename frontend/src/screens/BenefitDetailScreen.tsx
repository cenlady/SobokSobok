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
          className="primary-button"
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
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-cream/95 px-4 backdrop-blur-sm">
        <button onClick={() => navigate(-1)} className="p-1 text-brand-dark active:opacity-60">
          <ChevronLeft size={23} />
        </button>
        <h1 className="text-base font-semibold text-brand-dark">혜택 상세</h1>
        <button onClick={() => toggle(benefit.id)} className="p-1">
          <Bookmark
            size={24}
            className={has(benefit.id) ? 'fill-brand text-brand' : 'text-brand-dark/40'}
          />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-5 pb-28 pt-5">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className={`font-semibold ${meta.text}`}>
            {meta.label}
          </span>
          <span className="font-bold text-status-red">
            {ddayLabel(benefit.dueDate)}
          </span>
        </div>

        <h2 className="mt-4 text-2xl font-bold leading-snug text-brand-dark">
          {benefit.title}
        </h2>

        {benefit.amount && (
          <div className="mt-4 border-l-2 border-status-green pl-3">
            <span className="text-lg font-bold text-status-green">{benefit.amount}</span>
          </div>
        )}

        <div className="surface-panel mt-6 divide-y divide-line overflow-hidden">
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

        <h3 className="mt-8 border-t border-line pt-7 text-base font-bold text-brand-dark">지원 내용</h3>
        <p className="mt-3 whitespace-pre-line text-[15px] leading-[1.75] text-brand-dark/75">
          {benefit.content ?? benefit.summary}
        </p>
      </div>

      {/* 하단 고정 CTA */}
      <div className="absolute bottom-0 left-0 right-0 border-t border-line bg-surface px-5 py-3">
        <button className="primary-button w-full py-3.5 text-base">
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
    <div className="flex items-start gap-3 px-4 py-3.5">
      <Icon size={17} className="mt-0.5 text-brand" />
      <span className="w-12 text-sm text-muted">{label}</span>
      <span className="min-w-0 text-sm font-medium leading-relaxed text-brand-dark">{value}</span>
    </div>
  )
}
