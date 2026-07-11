import type { SavedPolicy } from '../types'

export function localDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function toDateKey(value?: string | null) {
  if (!value) return null
  return value.slice(0, 10)
}

export function formatDate(value?: string | null) {
  const dateKey = toDateKey(value)
  return dateKey ? dateKey.replaceAll('-', '.') : '미정'
}

export function addDays(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T00:00:00`)
  date.setDate(date.getDate() + days)
  return localDateKey(date)
}

function googleDate(value: string) {
  return value.replaceAll('-', '')
}

export function buildGoogleCalendarUrl(policy: SavedPolicy) {
  const start = toDateKey(policy.apply_end) || toDateKey(policy.apply_start) || localDateKey()
  const end = addDays(start, 1)
  const details = [
    policy.summary,
    policy.organization ? `기관: ${policy.organization}` : null,
    policy.support_type ? `지원유형: ${policy.support_type}` : null,
    policy.apply_url ? `신청 페이지: ${policy.apply_url}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: `[소복소복] ${policy.title}`,
    dates: `${googleDate(start)}/${googleDate(end)}`,
    details,
  })

  return `https://calendar.google.com/calendar/render?${params.toString()}`
}
