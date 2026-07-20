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

export type AiModelMode = 'cloud' | 'local'

export interface AiModelModes {
  chat: AiModelMode
  recommend: AiModelMode
  policySummary: AiModelMode
  calendarCoach: AiModelMode
  documentReview: AiModelMode
}

export interface Profile {
  ownerName: string
  storeName: string
  aiModelModes: AiModelModes
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
  apply_start?: string | null
  apply_end?: string | null
  /** 상시 접수(open)와 기간 확인 필요(notice)를 가른다 */
  status?: string | null
  eligibility_status: 'eligible' | 'needs_review'
  preference_match: 'exact' | 'partial' | 'none' | 'not_requested'
  match_status: 'eligible' | 'needs_review' | 'near_match'
  confidence: 'high' | 'medium' | 'low'
  rank_score: number
  vector_similarity?: number | null
  reasons: string[]
  warnings: string[]
  unknown_conditions: string[]
  unmet_conditions: string[]
  matched_tags: Record<string, string[]>
}

export interface RecommendationPreviewResponse {
  chat_session_id?: string | null
  total_candidates: number
  filtered_candidates: number
  returned: number
  skip: number
  limit: number
  has_next: boolean
  status_counts: Record<'eligible' | 'needs_review' | 'near_match', number>
  schedule_counts: Record<'period' | 'ongoing' | 'unknown', number>
  vector_used: boolean
  profile_warnings: string[]
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
  chat_model_mode: AiModelMode
  recommend_model_mode: AiModelMode
  policy_summary_model_mode: AiModelMode
  calendar_coach_model_mode: AiModelMode
  document_review_model_mode: AiModelMode
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
  model_mode: AiModelMode
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

/**
 * 서류 발급 가이드 — 어디서 어떻게 떼는가.
 *
 * 소상공인이 지원금을 못 받는 이유는 '무슨 서류가 필요한지 몰라서'만이 아니다.
 * 이름을 알아도 '어디서 어떻게 떼는지' 몰라서 못 낸다. 목록만 던지는 건 절반이다.
 */
export interface DocumentGuide {
  issuer: string
  online: string | null
  online_url: string | null
  offline: string | null
  duration: string
  fee: string
  tip: string | null
}

export interface RequirementMatch {
  document_name: string
  best_similarity: number
  /** 확정이 아니라 후보다 */
  likely_covered: boolean
  /** 이 요건을 커버하는 것으로 보이는 파일명 */
  matched_file: string | null
  /** 아직 정리되지 않은 서류면 null */
  guide: DocumentGuide | null
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
  model_mode: AiModelMode
  requirement_status: RequirementStatus
  requirement_matches: RequirementMatch[]
  files: ReviewFile[]
  /** 진행 중이면 null */
  summary: string | null
  /** 실패 시 내부 원문 대신 내려오는 안전한 오류 코드 */
  error_code: string | null
}

export interface RecommendationExplanationResponse {
  match_status: 'eligible' | 'needs_review' | 'near_match' | 'ineligible'
  eligibility_status: 'eligible' | 'needs_review' | 'ineligible'
  preference_match: 'exact' | 'partial' | 'none' | 'not_requested'
  confidence: 'high' | 'medium' | 'low'
  generated_by: 'rules' | 'openai' | 'ollama' | 'gemini'
  summary: string
  strengths: string[]
  aspects_to_check: string[]
  next_actions: string[]
  evidence: string[]
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

export interface ChatPolicyCandidate {
  policy_id: string
  title: string
  summary?: string | null
  support_type?: string | null
  apply_end?: string | null
  score: number
  source_count: number
}

export interface ChatAnswerResponse {
  query: string
  expanded_query: string
  intent_tags: string[]
  response_mode: 'answer' | 'policy_selection' | 'out_of_scope' | 'no_result'
  candidates: ChatPolicyCandidate[]
  sources: ChatChunkSource[]
  answer: string
  session_id: string
  context_policy_id?: string | null
  active_policy_id?: string | null
}

export interface ChatSessionResponse {
  session_id: string
  active_policy_id?: string | null
}

export interface ChatHistoryPolicy {
  policy_id: string
  title: string
  summary?: string | null
  support_type?: string | null
  apply_end?: string | null
}

export interface ChatHistorySession {
  session_id: string
  title: string
  preview: string
  message_count: number
  active_policy?: ChatHistoryPolicy | null
  created_at: string
  updated_at: string
}

export interface ChatHistoryListResponse {
  items: ChatHistorySession[]
  total: number
  skip: number
  limit: number
  has_next: boolean
}

export interface ChatHistoryMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  policy_id?: string | null
  policy_title?: string | null
  response_mode?: string | null
  candidates: Record<string, unknown>[]
  sources: ChatChunkSource[]
  created_at: string
}

export interface ChatHistoryDetailResponse {
  session: ChatHistorySession
  messages: ChatHistoryMessage[]
}
