import type { BenefitStatus } from '../types'

// 앱 기준 "오늘" (목업 데이터 기준일과 맞춤)
export const TODAY = '2024-06-17'

export function ddayLabel(dueDate: string, base: string = TODAY): string {
  const d1 = new Date(base + 'T00:00:00')
  const d2 = new Date(dueDate + 'T00:00:00')
  const diff = Math.round((d2.getTime() - d1.getTime()) / 86400000)
  if (diff === 0) return 'D-Day'
  return diff > 0 ? `D-${diff}` : `D+${-diff}`
}

export const statusMeta: Record<
  BenefitStatus,
  { label: string; text: string; bar: string; iconBg: string; iconColor: string }
> = {
  closing: {
    label: '오늘 마감',
    text: 'text-status-red',
    bar: 'bg-status-red',
    iconBg: 'bg-red-50',
    iconColor: 'text-status-red',
  },
  open: {
    label: '접수 시작',
    text: 'text-status-green',
    bar: 'bg-status-green',
    iconBg: 'bg-green-50',
    iconColor: 'text-status-green',
  },
  notice: {
    label: '안내/공고',
    text: 'text-status-blue',
    bar: 'bg-status-blue',
    iconBg: 'bg-blue-50',
    iconColor: 'text-status-blue',
  },
}
