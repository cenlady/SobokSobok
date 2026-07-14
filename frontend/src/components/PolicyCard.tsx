import { Bookmark, BookmarkCheck, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ddayLabel } from '../lib/format'
import { toDateKey } from '../lib/calendar'
import { NEED_OPTIONS } from '../lib/recommend'

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

  return [...new Set(labels)].slice(0, 3)
}

export interface PolicyCardData {
  policy_id: string
  title: string
  summary?: string | null
  support_type?: string | null
  categories?: string[]
  apply_end?: string | null
  /** 추천 탭에서만 채워진다 */
  rank_score?: number
  match_status?: 'eligible' | 'needs_review'
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
 * 정책 카드. 정책 찾기의 세 탭(전체·추천·저장한)과 홈 달력이 모두 이것을 쓴다.
 * 셋 다 normalized_policies(UUID)를 다루므로 카드·저장·상세 경로를 공유할 수 있다.
 */
export default function PolicyCard({ policy, saved, onToggleSave, savePending }: Props) {
  const navigate = useNavigate()
  const deadline = toDateKey(policy.apply_end)
  const categoryLabel = policy.categories?.[0]
    ? NEED_OPTIONS.find((option) => option.tag === policy.categories?.[0])?.label || policy.categories[0]
    : null
  const supportLabel = policy.support_type
    ? getSupportTypeLabels(policy.support_type)[0]
    : null
  const goToDetail = () =>
    navigate(`/policy/${policy.policy_id}`, {
      // 추천 탭에서 온 경우 이유·경고를 함께 넘긴다. 서버 설명 생성이 실패했을 때
      // 상세 화면이 이걸로 폴백한다. 다른 탭에서는 undefined라 폴백만 일반 문구가 된다.
      state: policy.match_status ? { recommendation: policy } : undefined,
    })

  return (
    <article
      role="link"
      tabIndex={0}
      onClick={goToDetail}
      onKeyDown={(event) => {
        if (event.key === 'Enter') goToDetail()
      }}
      className="group cursor-pointer bg-surface px-4 py-4 outline-none transition-colors hover:bg-white focus-visible:bg-white"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-medium text-muted">
            <span>{categoryLabel || supportLabel || '지원 정책'}</span>
            {policy.match_status && (
              <>
                <span className="h-0.5 w-0.5 rounded-full bg-brand-dark/30" />
                <span
                  className={
                    policy.match_status === 'eligible' ? 'text-status-green' : 'text-status-blue'
                  }
                >
                  {policy.match_status === 'eligible' ? '조건 일치' : '추가 확인 필요'}
                </span>
              </>
            )}
          </div>
          <h4 className="mt-1.5 line-clamp-2 text-[15px] font-semibold leading-snug text-brand-dark">
            {policy.title}
          </h4>
          {policy.summary && (
            <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-muted">
              {policy.summary}
            </p>
          )}
        </div>

        <div className="flex flex-shrink-0 flex-col items-end gap-2">
          {deadline && (
            <span className="text-xs font-bold tabular-nums text-status-red">
              {ddayLabel(deadline)}
            </span>
          )}
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onToggleSave(policy.policy_id)
          }}
          onKeyDown={(event) => event.stopPropagation()}
          disabled={savePending}
          aria-label={saved ? '저장 해제' : '정책 저장'}
          className={`flex h-8 w-8 items-center justify-center rounded-md border transition-colors ${
            saved
              ? 'border-brand/20 bg-accent-soft text-brand'
              : 'border-line bg-transparent text-brand-dark/35'
          } active:bg-black/5 disabled:opacity-50`}
        >
          {saved ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}
        </button>
        </div>
      </div>

      {(policy.reasons?.length || policy.warnings?.length) && (
        <div className="mt-3 border-l-2 border-brand-light pl-3">
          <p className="text-[11px] font-semibold text-brand">내 정보와 맞는 조건</p>
          {policy.reasons?.[0] && (
            <p className="mt-1 text-xs leading-relaxed text-brand-dark/65">
              {policy.reasons[0]}
            </p>
          )}
          {policy.warnings?.[0] && (
            <p className="mt-1 text-xs leading-relaxed text-status-blue">{policy.warnings[0]}</p>
          )}
        </div>
      )}
      <span className="mt-3 flex items-center justify-end gap-0.5 text-[11px] font-medium text-brand-dark/45">
        공고 자세히 보기 <ChevronRight size={13} />
      </span>
    </article>
  )
}
