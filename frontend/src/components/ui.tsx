import { AlertCircle, AlertTriangle, CheckCircle2, ChevronLeft, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import type { DeadlineInfo } from '../lib/deadline'

// 화면 전반이 공유하는 최소 UI 조각들.
//
// 이전 화면들은 배지·버튼 스타일을 각자 인라인으로 적어서, 색만 다르고 급이 같은
// 배지가 카드 하나에 넷씩 붙었다. 여기서 '급'을 강제한다.

/* ─────────────────────── 화면 구조 ─────────────────────── */

interface ScreenHeaderProps {
  title: string
  onBack?: () => void
  backLabel?: string
  action?: ReactNode
  sticky?: boolean
}

/** 뒤로가기 화면의 공통 헤더. 좌우 슬롯을 고정해 제목이 항상 화면 중앙에 놓인다. */
export function ScreenHeader({
  title,
  onBack,
  backLabel = '뒤로',
  action,
  sticky = true,
}: ScreenHeaderProps) {
  return (
    <header
      className={`grid h-14 grid-cols-[44px_1fr_44px] items-center bg-cream/95 px-3 backdrop-blur ${
        sticky ? 'sticky top-0 z-10' : ''
      }`}
    >
      {onBack ? (
        <IconButton icon={ChevronLeft} onClick={onBack} label={backLabel} />
      ) : (
        <span aria-hidden="true" />
      )}
      <h1 className="truncate px-2 text-center text-[15px] font-semibold text-ink">{title}</h1>
      <div className="flex justify-end">{action}</div>
    </header>
  )
}

export function PageIntro({
  title,
  description,
  className = '',
}: {
  title: string
  description?: ReactNode
  className?: string
}) {
  return (
    <section className={`px-5 pt-2 ${className}`}>
      <h2 className="text-title text-ink">{title}</h2>
      {description && <p className="mt-1 text-sm leading-relaxed text-muted">{description}</p>}
    </section>
  )
}

export function Panel({
  children,
  divided = false,
  className = '',
}: {
  children: ReactNode
  divided?: boolean
  className?: string
}) {
  return (
    <div
      className={`surface-panel ${divided ? 'divide-y divide-line overflow-hidden' : ''} ${className}`}
    >
      {children}
    </div>
  )
}

type NoticeTone = 'neutral' | 'warning' | 'success' | 'error'

const NOTICE_STYLE: Record<NoticeTone, { box: string; icon: string; Icon: LucideIcon }> = {
  neutral: { box: 'border-line bg-surface', icon: 'text-subtle', Icon: Info },
  warning: { box: 'border-accent/25 bg-accent-soft/45', icon: 'text-brand', Icon: AlertTriangle },
  success: {
    box: 'border-status-green/20 bg-status-green/5',
    icon: 'text-status-green',
    Icon: CheckCircle2,
  },
  error: {
    box: 'border-status-red/20 bg-status-red/5',
    icon: 'text-status-red',
    Icon: AlertCircle,
  },
}

export function Notice({
  children,
  title,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  title?: string
  tone?: NoticeTone
  className?: string
}) {
  const { box, icon, Icon } = NOTICE_STYLE[tone]
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border p-4 ${box} ${className}`}>
      <Icon size={17} strokeWidth={1.8} className={`mt-0.5 shrink-0 ${icon}`} />
      <div className="min-w-0 text-sm leading-relaxed text-muted">
        {title && <p className="mb-1 font-semibold text-ink">{title}</p>}
        {children}
      </div>
    </div>
  )
}

export const fieldControlClass =
  'h-12 w-full rounded-xl border border-line bg-surface px-4 text-[15px] text-ink outline-none transition-colors placeholder:text-subtle focus:border-primary disabled:bg-line/40 disabled:text-subtle'

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string
  htmlFor?: string
  hint?: string
  error?: string | null
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-[15px] font-semibold text-ink">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs leading-relaxed text-muted">{hint}</p>}
      {error && <p className="mt-1.5 text-xs font-medium text-status-red">{error}</p>}
    </div>
  )
}

export function ChoiceChip({
  children,
  selected,
  onClick,
  variant = 'pill',
  className = '',
}: {
  children: ReactNode
  selected: boolean
  onClick: () => void
  variant?: 'pill' | 'compact'
  className?: string
}) {
  if (variant === 'compact') {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={selected}
        className={`inline-flex min-h-11 items-center justify-center text-xs font-semibold ${className}`}
      >
        <span
          className={`inline-flex h-9 w-full items-center justify-center rounded-xl border px-2 text-center leading-tight transition-colors ${
            selected
              ? 'border-primary bg-primary-soft text-primary'
              : 'border-line bg-surface text-muted active:bg-line/40'
          }`}
        >
          {children}
        </span>
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex min-h-11 items-center justify-center rounded-full border px-3 py-2 text-center text-xs font-semibold transition-colors ${
        selected
          ? 'border-primary bg-primary-soft text-primary'
          : 'border-line bg-surface text-muted active:bg-line/40'
      } ${className}`}
    >
      {children}
    </button>
  )
}

export function Pagination({
  page,
  pageCount,
  inputValue,
  onInputChange,
  onSubmit,
  onPrevious,
  onNext,
  previousDisabled,
  nextDisabled,
  label = '페이지',
}: {
  page: number
  pageCount: number
  inputValue: string
  onInputChange: (value: string) => void
  onSubmit: () => void
  onPrevious: () => void
  onNext: () => void
  previousDisabled: boolean
  nextDisabled: boolean
  label?: string
}) {
  const inputId = `pagination-${label.replace(/\s+/g, '-')}`
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-2 pt-1">
      <Button variant="secondary" size="sm" disabled={previousDisabled} onClick={onPrevious}>
        이전
      </Button>
      <div className="flex min-w-0 items-center justify-center gap-1.5">
        <label htmlFor={inputId} className="sr-only">
          이동할 {label}
        </label>
        <input
          id={inputId}
          type="number"
          inputMode="numeric"
          min={1}
          max={pageCount}
          value={inputValue}
          onChange={(event) => onInputChange(event.target.value.replace(/[^0-9]/g, ''))}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onSubmit()
          }}
          className="h-11 w-12 rounded-lg border border-line bg-surface px-1 text-center text-sm font-bold text-ink outline-none focus:border-primary"
        />
        <span className="whitespace-nowrap text-xs font-semibold text-muted">/ {pageCount}</span>
        <button
          type="button"
          onClick={onSubmit}
          className="h-11 rounded-lg bg-line/40 px-2.5 text-xs font-bold text-ink active:bg-line"
        >
          이동
        </button>
      </div>
      <Button variant="primary" size="sm" disabled={nextDisabled} onClick={onNext}>
        다음
      </Button>
      <span className="sr-only" aria-live="polite">
        현재 {page + 1}{label}
      </span>
    </div>
  )
}

/* ────────────────────────── 배지 ────────────────────────── */

/**
 * 상태 배지 — 카드당 '하나만'. 채운 형태.
 *
 * 마감 임박(빨강)이 눈에 띄려면 다른 곳에서 빨강을 쓰지 않아야 하고,
 * 상태 배지가 여럿이면 어느 것도 상태를 말해주지 못한다.
 */
export function StatusBadge({ info }: { info: DeadlineInfo }) {
  const style: Record<DeadlineInfo['kind'], string> = {
    urgent: 'bg-status-red text-white',
    dated: 'bg-ink text-white',
    always: 'bg-status-green/10 text-status-green',
    unknown: 'bg-line text-muted',
    closed: 'bg-line text-subtle',
  }

  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-[11px] font-bold tracking-tight ${style[info.kind]}`}
    >
      {info.label}
    </span>
  )
}

/**
 * 카테고리 태그 — 얇은 외곽선, 뉴트럴. 상태 배지보다 명백히 한 급 아래.
 * 최대 2개까지만 붙인다(TagList가 잘라낸다).
 */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded border border-line px-1.5 py-0.5 text-[11px] font-medium text-muted">
      {children}
    </span>
  )
}

export function TagList({ items, max = 2 }: { items: (string | null | undefined)[]; max?: number }) {
  const tags = items.filter((t): t is string => Boolean(t)).slice(0, max)
  if (tags.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Tag key={tag}>{tag}</Tag>
      ))}
    </div>
  )
}

/* ────────────────────────── 버튼 ────────────────────────── */

type ButtonVariant = 'primary' | 'secondary' | 'ghost'
type ButtonSize = 'sm' | 'md'

interface ButtonProps {
  children: ReactNode
  onClick?: () => void
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  full?: boolean
  type?: 'button' | 'submit'
  className?: string
  'aria-label'?: string
}

const VARIANT: Record<ButtonVariant, string> = {
  // 진흙빛 초콜릿(#6F4A12) 대신 채도 높은 테라코타. 밝기가 아니라 채도가 생기를 만든다.
  //
  // disabled는 '채도를 낮춘 primary'가 아니라 아예 다른 색이어야 한다. bg-primary/30
  // 같은 투명도는 색이 살아 있어 활성 버튼처럼 보인다. 회색 면 + 흐린 글자로 확실히 끈다.
  primary: 'bg-primary text-white active:bg-primary-hover disabled:bg-line disabled:text-subtle',
  secondary:
    'bg-surface text-ink border border-line active:bg-line/40 disabled:bg-line/40 disabled:text-subtle disabled:border-transparent',
  ghost: 'text-muted active:text-ink disabled:text-subtle',
}

// 최소 높이 44px — 손가락이 닿는 영역의 하한이다.
const SIZE: Record<ButtonSize, string> = {
  sm: 'h-11 px-3.5 text-[13px] font-semibold rounded-lg gap-1',
  md: 'h-12 px-5 text-[15px] font-bold rounded-xl gap-1.5',
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled,
  full,
  type = 'button',
  className = '',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center transition-colors active:scale-[0.99] disabled:pointer-events-none ${VARIANT[variant]} ${SIZE[size]} ${full ? 'w-full' : ''} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

/* ────────────────────── 아이콘 버튼 ────────────────────── */

interface IconButtonProps {
  icon: LucideIcon
  onClick?: () => void
  label: string
  disabled?: boolean
  /** 눌린 상태 (저장됨 등) */
  active?: boolean
  className?: string
}

/**
 * 아이콘만 있는 버튼.
 *
 * 달력 화살표·북마크·연필처럼 눈에 보이는 크기가 작은 버튼들이 터치 영역까지 작으면
 * 누르기가 어렵다. 보이는 크기와 무관하게 손가락이 닿는 영역은 44×44를 보장한다.
 */
export function IconButton({
  icon: Icon,
  onClick,
  label,
  disabled,
  active,
  className = '',
}: IconButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors active:scale-95 disabled:pointer-events-none disabled:text-faint ${
        active ? 'bg-accent-soft text-brand' : 'text-muted active:bg-line/50'
      } ${className}`}
    >
      <Icon size={20} strokeWidth={1.9} />
    </button>
  )
}

/* ──────────────────────── 빈 상태 ──────────────────────── */

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

/**
 * 빈 상태 — 텍스트 한 줄로 끝내지 않는다. 여기가 이탈이 제일 많이 나는 지점이다.
 * 큰 뉴트럴 아이콘 + 설명 + 다음 행동. 귀여운 캐릭터를 넣지 않는다.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <Icon size={40} strokeWidth={1.5} className="text-faint" />
      <p className="mt-4 text-[15px] font-semibold text-ink">{title}</p>
      {description && (
        <p className="mt-1.5 max-w-[260px] text-sm leading-relaxed text-muted">{description}</p>
      )}
      {actionLabel && onAction && (
        <Button onClick={onAction} size="sm" className="mt-5">
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

/* ──────────────────────── 로딩 ──────────────────────── */

export function LoadingLine({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2.5 px-1 py-6 text-sm text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line border-t-muted" />
      {message}
    </div>
  )
}
