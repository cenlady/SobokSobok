import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import type { DeadlineInfo } from '../lib/deadline'

// 화면 전반이 공유하는 최소 UI 조각들.
//
// 이전 화면들은 배지·버튼 스타일을 각자 인라인으로 적어서, 색만 다르고 급이 같은
// 배지가 카드 하나에 넷씩 붙었다. 여기서 '급'을 강제한다.

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
  primary: 'bg-primary text-white active:bg-primary-hover disabled:bg-subtle',
  secondary: 'bg-white text-ink border border-line active:bg-line/40 disabled:text-subtle',
  ghost: 'text-muted active:text-ink disabled:text-subtle',
}

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-[13px] font-semibold rounded-lg gap-1',
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
      <Icon size={40} strokeWidth={1.5} className="text-subtle" />
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
