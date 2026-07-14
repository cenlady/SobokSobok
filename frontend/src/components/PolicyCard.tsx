import { AlertCircle, ArrowRight, Bookmark, BookmarkCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getDeadlineInfo } from '../lib/deadline'
import { NEED_OPTIONS } from '../lib/recommend'
import { Button, StatusBadge, TagList } from './ui'

const SUPPORT_TYPE_LABELS: Record<string, string> = {
  현금: '현금 지원',
  비현금: '서비스 지원',
  현물: '현물 지원',
  융자: '융자',
  보조금: '보조금',
}

function getSupportTypeLabels(value: string) {
  const tokens = value
    .replace(/기타\(([^)]*)\)/g, ' $1 ')
    .split(/[,/|·;\s]+/)
    .map((token) => token.trim())
    .filter(Boolean)

  const labels = tokens
    .filter((token) => token !== '기타')
    .map((token) => SUPPORT_TYPE_LABELS[token] || token)
    .filter((token) => token.length <= 12)

  return [...new Set(labels)]
}

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
  match_status?: 'eligible' | 'needs_review' | 'near_match'
  reasons?: string[]
  warnings?: string[]
}

interface Props {
  policy: PolicyCardData
  saved: boolean
  onToggleSave: (policyId: string) => void
  /** 저장 토글이 서버 왕복 중일 때 */
  savePending?: boolean
}

/**
 * 정책 카드. 정책 찾기의 세 탭과 홈이 모두 이것을 쓴다.
 *
 * 배지에 급을 매긴다. 예전에는 상태·유형·마감일 배지가 색만 다르고 급이 같아
 * 카드 하나에 넷씩 붙었고, 그래서 어느 것도 눈에 들어오지 않았다.
 *
 *   1급 — 상태 배지: 딱 하나. 채운 형태. (D-3 / 상시 접수 / 기간 확인 필요)
 *   2급 — 카테고리 태그: 최대 둘. 얇은 외곽선, 뉴트럴.
 *
 * '추천 가능'은 빼고 '확인 필요'만 남긴다. 추천 탭에 뜬 정책이 추천 가능한 건
 * 당연해서 정보량이 없다. 예외만 말하는 편이 정보량이 크다.
 */
export default function PolicyCard({ policy, saved, onToggleSave, savePending }: Props) {
  const navigate = useNavigate()
  const deadline = getDeadlineInfo(policy)
  const needsReview = policy.match_status === 'needs_review'

  const categoryLabels = policy.categories?.length
    ? policy.categories.map(
        (category) => NEED_OPTIONS.find((option) => option.tag === category)?.label || category,
      )
    : policy.support_type
      ? getSupportTypeLabels(policy.support_type)
      : []

  return (
    <article className="rounded-2xl bg-white p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <StatusBadge info={deadline} />

          <h4 className="mt-2 line-clamp-2 text-card text-ink">{policy.title}</h4>

          {policy.summary && (
            <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">
              {policy.summary}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => onToggleSave(policy.policy_id)}
          disabled={savePending}
          aria-label={saved ? '저장 해제' : '정책 저장'}
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors active:scale-95 disabled:opacity-50 ${
            saved ? 'bg-accent-soft text-accent' : 'bg-line/50 text-subtle'
          }`}
        >
          {saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}
        </button>
      </div>

      {categoryLabels.length > 0 && (
        <div className="mt-3">
          <TagList items={categoryLabels} max={2} />
        </div>
      )}

      {/* 추천 이유는 한 줄만. 여러 줄이면 카드가 아니라 문서가 된다. */}
      {policy.reasons?.[0] && (
        <p className="mt-3 line-clamp-1 text-xs text-subtle">{policy.reasons[0]}</p>
      )}

      {needsReview && (
        <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-muted">
          <AlertCircle size={13} className="mt-px shrink-0 text-subtle" />
          {policy.warnings?.[0] || '지원 조건을 다시 확인해보세요'}
        </p>
      )}

      <Button
        onClick={() =>
          navigate(`/policy/${policy.policy_id}`, {
            // 추천 탭에서 온 경우 이유·경고를 함께 넘긴다. 서버 설명 생성이 실패했을 때
            // 상세 화면이 이걸로 폴백한다.
            state: policy.match_status ? { recommendation: policy } : undefined,
          })
        }
        size="sm"
        full
        className="mt-3"
      >
        상세보기 <ArrowRight size={14} />
      </Button>
    </article>
  )
}
