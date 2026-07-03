// 소복소복 공통 타입 정의

export type BenefitStatus = 'closing' | 'open' | 'notice'
// closing: 마감 임박, open: 접수 시작, notice: 안내/공고

export interface Benefit {
  id: string
  title: string
  summary: string
  status: BenefitStatus
  amount?: string // 예: "최대 20만원"
  dueDate: string // ISO date (YYYY-MM-DD) — 마감/기준일
  startDate?: string
  endDate?: string
  category: string // 업종/분야
  region?: string
  timeLabel?: string // 예: "오후 6시까지", "오전 10시"
  content?: string // 상세 본문
}

export interface Profile {
  ownerName: string
  storeName: string
  industry: string // 업종
  region: string // 활동 지역
  revenue: string // 연매출 규모
  employees: string // 직원 수
}
