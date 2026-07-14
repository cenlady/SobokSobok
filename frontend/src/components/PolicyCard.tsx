import { AlertCircle, Bookmark, BookmarkCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getDeadlineInfo } from '../lib/deadline'
import { getPolicyLabels } from '../lib/policyLabels'
import { StatusBadge, TagList } from './ui'

export interface PolicyCardData {
  policy_id: string
  title: string
  summary?: string | null
  support_type?: string | null
  categories?: string[]
  apply_end?: string | null
  /** 상시 접수인지 기간 미상인지를 가른다 (open | notice | closed) */
  status?: string | null
  /** 추천 탭에서만 채워진다 */
  rank_score?: number
  eligibility_status?: 'eligible' | 'needs_review'
  preference_match?: 'exact' | 'partial' | 'none' | 'not_requested'
  match_status?: 'eligible' | 'needs_review' | 'near_match'
  reasons?: string[]
  warnings?: string[]
  unmet_conditions?: string[]
}

interface Props {
  policy: PolicyCardData
  saved: boolean
  onToggleSave: (policyId: string) => void
  /** 저장 토글이 서버 왕복 중일 때 */
  savePending?: boolean
}

/**
 * 정책 목록의 한 행.
 *
 * 카드마다 '상세보기' 버튼을 달지 않는다. 정책 30건을 훑는 화면에서 버튼이 30개면
 * 그것만으로 화면이 꽉 찬다. 행 전체를 누를 수 있게 하고, 저장 버튼만 따로 둔다.
 *
 * 배지에는 급을 매긴다. 예전에는 상태·유형·마감일 배지가 색만 다르고 급이 같이
 * 넷씩 붙어서, 결국 어느 것도 눈에 들어오지 않았다.
 *   1급 — 상태 배지: 딱 하나. 채운 형태.
 *   2급 — 카테고리 태그: 최대 둘. 얇은 외곽선, 뉴트럴.
 */
export default function PolicyCard({ policy, saved, onToggleSave, savePending }: Props) {
  const navigate = useNavigate()
  const deadline = getDeadlineInfo(policy)
  const needsReview =
    policy.eligibility_status === 'needs_review' || policy.match_status === 'needs_review'
  const isPreferenceMismatch =
    policy.preference_match === 'none' || policy.match_status === 'near_match'

  const categoryLabels = getPolicyLabels(policy)

  const goToDetail = () =>
    navigate(`/policy/${policy.policy_id}`, {
      // 추천 탭에서 온 경우 이유·경고를 함께 넘긴다. 서버 설명 생성이 실패했을 때
      // 상세 화면이 이걸로 폴백한다.
      state: policy.match_status ? { recommendation: policy } : undefined,
    })

  return (
    <article
      role="link"
      tabIndex={0}
      onClick={goToDetail}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          goToDetail()
        }
      }}
      className="cursor-pointer px-4 py-4 outline-none transition-colors hover:bg-cream/60 focus-visible:bg-cream/60 active:bg-cream"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <StatusBadge info={deadline} />

          <h4 className="mt-2 line-clamp-2 text-card text-ink">{policy.title}</h4>

          {categoryLabels.length > 0 && (
            <div className="mt-1.5">
              <TagList items={categoryLabels} max={2} />
            </div>
          )}

          {policy.summary && (
            <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-muted">
              {policy.summary}
            </p>
          )}
        </div>

        {/* 행 전체가 링크이므로 저장 버튼은 클릭이 위로 새지 않게 막는다. */}
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onToggleSave(policy.policy_id)
          }}
          onKeyDown={(event) => event.stopPropagation()}
          disabled={savePending}
          aria-label={saved ? '저장 해제' : '정책 저장'}
          className={`-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors active:scale-95 disabled:pointer-events-none disabled:text-faint ${
            saved ? 'text-brand' : 'text-subtle hover:text-muted'
          }`}
        >
          {saved ? <BookmarkCheck size={19} /> : <Bookmark size={19} />}
        </button>
      </div>

      {/* 추천 이유는 한 줄만. 여러 줄이면 목록이 아니라 문서가 된다. */}
      {policy.reasons?.[0] && (
        <p className="mt-2.5 line-clamp-1 border-l-2 border-line pl-2.5 text-xs text-subtle">
          {policy.reasons[0]}
        </p>
      )}

      {(needsReview || isPreferenceMismatch) && (
        <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-muted">
          <AlertCircle size={13} className="mt-px shrink-0 text-subtle" />
          {needsReview
            ? policy.warnings?.[0] || '지원 자격 조건을 다시 확인해보세요'
            : policy.unmet_conditions?.[0] || '선택한 관심 분야와 직접 일치하지 않습니다'}
        </p>
      )}
    </article>
  )
}
