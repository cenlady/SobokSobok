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
  industryTags: string[]
  region: string // 활동 지역
  regionSido: string
  regionSigungu: string
  revenue: string // 연매출 규모
  revenueRange: {
    min: number | null
    max: number | null
  } | null
  employees: string // 직원 수
  employeesRange: {
    min: number | null
    max: number | null
  } | null
  businessStatus: string
  businessStatusTags: string[]
  businessAge: string
  businessAgeYears: {
    min: number | null
    max: number | null
  } | null
  needTags: string[]
}

export interface RecommendationResult {
  policy_id: string
  title: string
  summary?: string | null
  organization?: string | null
  support_type?: string | null
  support_content?: string | null
  apply_url?: string | null
  apply_end?: string | null
  match_status: 'eligible' | 'needs_review' | 'near_match'
  confidence: 'high' | 'medium' | 'low'
  rank_score: number
  vector_similarity?: number | null
  score_breakdown: Record<string, number>
  reasons: string[]
  warnings: string[]
  unknown_conditions: string[]
  unmet_conditions: string[]
  matched_tags: Record<string, string[]>
}

export interface RecommendationPreviewResponse {
  total_candidates: number
  returned: number
  vector_used: boolean
  results: RecommendationResult[]
}

export interface PolicyDetailResponse {
  id: string
  source: string
  source_pk: string
  title: string
  summary?: string | null
  body?: string | null
  organization?: string | null
  support_type?: string | null
  target_text?: string | null
  support_content?: string | null
  region_scope: string
  sido?: string | null
  sigungu?: string | null
  matched_sidos: string[]
  status?: string | null
  apply_start?: string | null
  apply_end?: string | null
  apply_url?: string | null
  application_methods: string[]
  contact_points: unknown[]
  industry_tags: string[]
  business_status_tags: string[]
  eligibility: Record<string, unknown>
  required_documents: unknown[]
  attachments?: PolicyAttachment[]
}

export interface PolicyAttachment {
  attachment_file_id: string
  original_file_name: string | null
}

export interface SavedPolicy {
  policy_id: string
  title: string
  summary?: string | null
  organization?: string | null
  support_type?: string | null
  apply_start?: string | null
  apply_end?: string | null
  apply_url?: string | null
  rank_score?: number
  match_status?: 'eligible' | 'needs_review' | 'near_match'
  reasons?: string[]
  warnings?: string[]
  saved_at: string
}

export interface RecommendationExplanationResponse {
  summary: string
  strengths: string[]
  aspects_to_check: string[]
  next_actions: string[]
}
