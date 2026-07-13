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
  match_status: 'eligible' | 'needs_review'
  confidence: 'high' | 'medium' | 'low'
  rank_score: number
  vector_similarity?: number | null
  reasons: string[]
  warnings: string[]
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

/** 서버에 저장된 즐겨찾기 1건 (GET /api/v1/favorites) */
export interface SavedPolicy {
  policy_id: string
  title: string
  summary?: string | null
  organization?: string | null
  support_type?: string | null
  region_scope: string
  sido?: string | null
  sigungu?: string | null
  status?: string | null
  apply_start?: string | null
  apply_end?: string | null
  apply_url?: string | null
  saved_at: string
  categories?: string[]
}

export interface UserMe {
  id: number
  email: string
  is_active: boolean
  /** false면 온보딩으로 보내야 한다 */
  onboarded: boolean
}

/** 서버 프로필 (GET/PUT /api/v1/users/me/profile). 추천 요청과 1:1로 대응한다. */
export interface ServerProfile {
  owner_name?: string | null
  store_name?: string | null
  region?: { sido?: string | null; sigungu?: string | null } | null
  industry: { label?: string | null; tags: string[] }
  business_status: { label?: string | null; tags: string[] }
  annual_sales: { label?: string | null; min?: number | null; max?: number | null }
  employees: { label?: string | null; min?: number | null; max?: number | null }
  business_age: { label?: string | null; min?: number | null; max?: number | null }
  need_tags: string[]
  onboarded_at?: string | null
}

/** 서류검토 접수 응답 (POST /api/v1/review → 202) */
export interface ReviewStartResponse {
  upload_id: string
  policy_id: string | null
  review_status: ReviewStatus
  /** policy_id가 있어 요건 대조 단계를 거치는지. 진행 단계 수를 결정한다. */
  has_requirement_matching: boolean
}

export type ReviewStatus =
  | 'queued'
  | 'extracting'
  | 'matching'
  | 'diagnosing'
  | 'done'
  | 'failed'

export interface RequirementMatch {
  document_name: string
  best_similarity: number
  /** 임계값 이상이면 true. 확정이 아니라 후보다 — 최종 판정은 LLM이 한다. */
  likely_covered: boolean
}

export interface ReviewResult {
  document_type: string
  typos: string[]
  /** 이 서류 안의 빈칸 (연락처·서명 등) */
  missing_fields: string[]
  format_issues: string[]
  /** 따로 발급받아 제출해야 하는 서류 */
  missing_documents: string[]
  improvement_points: string[]
  overall: string
}

/** 서류검토 폴링 응답 (GET /api/v1/review/{upload_id}) */
export interface ReviewResponse {
  upload_id: string
  policy_id: string | null
  review_status: ReviewStatus
  /** 실패 사유 (unsupported/empty/failed) */
  extraction_status: string
  requirement_matches: RequirementMatch[]
  /** 진행 중이면 null */
  result: ReviewResult | null
}

export interface RecommendationExplanationResponse {
  summary: string
  strengths: string[]
  aspects_to_check: string[]
  next_actions: string[]
}

export interface ChatChunkSource {
  chunk_id: string
  policy_id: string
  document_id: string
  chunk_index: number
  similarity: number
  rerank_score?: number | null
  chunk_text: string
  policy_title?: string | null
  document_type?: string | null
  document_title?: string | null
  source_ref?: string | null
}

export interface ChatAnswerResponse {
  query: string
  expanded_query: string
  intent_tags: string[]
  sources: ChatChunkSource[]
  answer: string
  langsmith_enabled: boolean
  langsmith_project?: string | null
}
