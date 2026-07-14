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
  /** 상시 접수(open)와 기간 확인 필요(notice)를 가른다 */
  status?: string | null
  match_status: 'eligible' | 'needs_review' | 'near_match'
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
  session_id: string
  policy_id: string | null
  review_status: ReviewStatus
  file_count: number
  /**
   * 요건 대조 단계를 실제로 거치는지. 진행 단계 수를 결정한다.
   * 정책을 골랐어도 그 정책에 필수서류 정보가 없으면(전체의 63%) false다.
   */
  has_requirement_matching: boolean
}

export type ReviewStatus =
  | 'queued'
  | 'extracting'
  | 'diagnosing'
  | 'matching'
  | 'done'
  | 'failed'

/**
 * 요건 대조를 '할 수 있었는지'.
 *
 * requirement_matches가 비었다고 해서 요건을 다 충족한 게 아니다 — 애초에 요건
 * 정보가 없었을 수 있다. 둘을 뭉뚱그리면 사용자를 근거 없이 안심시키게 된다.
 */
export type RequirementStatus = 'not_requested' | 'no_requirement_data' | 'matched'

export interface RequirementMatch {
  document_name: string
  best_similarity: number
  /** 확정이 아니라 후보다 */
  likely_covered: boolean
  /** 이 요건을 커버하는 것으로 보이는 파일명 */
  matched_file: string | null
}

/** 파일 하나의 자체 검토 결과. 요건 대조는 여기 없다 — 그건 세션 전체 기준이다. */
export interface FileDiagnosis {
  document_type: string
  typos: string[]
  /** 이 서류 안의 빈칸 (연락처·서명 등) */
  missing_fields: string[]
  format_issues: string[]
  improvement_points: string[]
  overall: string
}

export interface ReviewFile {
  upload_id: string
  file_name: string | null
  /** pending / success / empty / unsupported / failed */
  extraction_status: string
  /** 아직 진단 전이거나 읽기에 실패했으면 null */
  diagnosis: FileDiagnosis | null
}

/** 서류검토 폴링 응답 (GET /api/v1/review/{session_id}) */
export interface ReviewResponse {
  session_id: string
  policy_id: string | null
  review_status: ReviewStatus
  requirement_status: RequirementStatus
  requirement_matches: RequirementMatch[]
  files: ReviewFile[]
  /** 진행 중이면 null */
  summary: string | null
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
