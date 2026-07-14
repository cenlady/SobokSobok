// 정책의 접수 기간을 사람이 읽을 수 있는 하나의 상태로 판정한다.
//
// 예전에는 apply_end가 null이면 무조건 '미정'을 뱉어서 화면에 "미정 ~ 미정"이 그대로
// 노출됐다. 그런데 마감일이 없는 정책은 성격이 전혀 다른 두 부류가 섞여 있다.
//
//   status='open'   + 마감일 없음  →  상시신청 (176건). 마감이 없다는 게 '확정'이다.
//   status='notice' + 마감일 없음  →  "접수기관 별 상이"/"별도 안내". 우리가 '모른다'.
//
// 둘을 뭉뚱그려 '미정'이라 부르면, 좋은 소식(언제든 신청 가능)을 실패처럼 보이게 만들고
// 모르는 것을 아는 척하게 된다. 정규화가 이미 status로 구분해 뒀으니 그걸 쓴다.

import { toDateKey } from './calendar'

export type DeadlineKind =
  | 'urgent' // 마감 D-7 이내
  | 'dated' // 마감일 있음
  | 'always' // 상시 접수 (마감 없음이 확정)
  | 'unknown' // 기간 확인 필요 (우리가 모름)
  | 'closed' // 마감됨

export interface DeadlineInfo {
  kind: DeadlineKind
  /** 배지에 쓸 짧은 문구 */
  label: string
  /** 마감까지 남은 일수 (dated/urgent일 때만) */
  daysLeft?: number
  /** 캘린더에 등록할 수 있는가 (날짜가 있어야 가능) */
  calendarable: boolean
}

const URGENT_DAYS = 7

interface PolicyLike {
  apply_end?: string | null
  status?: string | null
}

export function getDeadlineInfo(policy: PolicyLike, today = new Date()): DeadlineInfo {
  if (policy.status === 'closed') {
    return { kind: 'closed', label: '마감', calendarable: false }
  }

  const endKey = toDateKey(policy.apply_end)

  if (!endKey) {
    // 마감일이 없다. status가 '이게 좋은 소식인지 모르는 것인지'를 알려준다.
    return policy.status === 'open'
      ? { kind: 'always', label: '상시 접수', calendarable: false }
      : { kind: 'unknown', label: '기간 확인 필요', calendarable: false }
  }

  const days = daysBetween(today, endKey)

  if (days < 0) {
    return { kind: 'closed', label: '마감', calendarable: false }
  }

  return {
    kind: days <= URGENT_DAYS ? 'urgent' : 'dated',
    label: days === 0 ? 'D-DAY' : `D-${days}`,
    daysLeft: days,
    calendarable: true,
  }
}

function daysBetween(from: Date, toKey: string): number {
  const start = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  const end = new Date(`${toKey}T00:00:00`)
  return Math.round((end.getTime() - start.getTime()) / 86_400_000)
}

/**
 * 접수 기간 한 줄. 날짜가 없으면 null을 돌려주고, 화면은 그 줄을 통째로 숨긴다.
 * "미정 ~ 미정" 같은 문구를 만들지 않는다.
 */
export function formatPeriod(policy: {
  apply_start?: string | null
  apply_end?: string | null
}): string | null {
  const start = toDateKey(policy.apply_start)
  const end = toDateKey(policy.apply_end)

  if (!start && !end) return null

  const dot = (key: string) => key.replaceAll('-', '.')
  if (start && end) return `${dot(start)} ~ ${dot(end)}`
  if (end) return `${dot(end)} 마감`
  return `${dot(start!)} 시작`
}
