import { ArrowRight, Bookmark, BookmarkCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ddayLabel } from '../lib/format'
import { toDateKey } from '../lib/calendar'

export interface PolicyCardData {
  policy_id: string
  title: string
  summary?: string | null
  support_type?: string | null
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

  return (
    <article className="rounded-2xl bg-white p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {policy.match_status && (
              <span
                className={`rounded-lg px-2 py-0.5 text-xs font-bold ${
                  policy.match_status === 'eligible'
                    ? 'bg-green-50 text-status-green'
                    : 'bg-blue-50 text-status-blue'
                }`}
              >
                {policy.match_status === 'eligible' ? '추천 가능' : '확인 필요'}
              </span>
            )}
            {policy.support_type && (
              <span className="rounded-lg bg-brand-light/20 px-2 py-0.5 text-xs font-semibold text-brand">
                {policy.support_type}
              </span>
            )}
            {deadline && (
              <span className="rounded-lg bg-red-50 px-2 py-0.5 text-xs font-bold text-status-red">
                {ddayLabel(deadline)}
              </span>
            )}
          </div>
          <h4 className="mt-2 line-clamp-2 text-base font-bold leading-snug text-brand-dark">
            {policy.title}
          </h4>
        </div>

        <button
          type="button"
          onClick={() => onToggleSave(policy.policy_id)}
          disabled={savePending}
          aria-label={saved ? '저장 해제' : '정책 저장'}
          className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full transition-colors ${
            saved ? 'bg-accent-soft text-accent' : 'bg-black/[0.04] text-brand-dark/40'
          } active:scale-95 disabled:opacity-50`}
        >
          {saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}
        </button>
      </div>

      {policy.summary && (
        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-brand-dark/60">
          {policy.summary}
        </p>
      )}

      {(policy.reasons?.length || policy.warnings?.length) && (
        <div className="mt-3 space-y-1">
          {policy.reasons?.slice(0, 2).map((reason) => (
            <p key={reason} className="text-xs font-medium text-brand-dark/60">
              {reason}
            </p>
          ))}
          {policy.warnings?.[0] && (
            <p className="text-xs font-medium text-status-blue">{policy.warnings[0]}</p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() =>
          navigate(`/policy/${policy.policy_id}`, {
            // 추천 탭에서 온 경우 이유·경고를 함께 넘긴다. 서버 설명 생성이 실패했을 때
            // 상세 화면이 이걸로 폴백한다. 다른 탭에서는 undefined라 폴백만 일반 문구가 된다.
            state: policy.match_status ? { recommendation: policy } : undefined,
          })
        }
        className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-dark py-2.5 text-sm font-semibold text-white active:scale-[0.99]"
      >
        상세보기 <ArrowRight size={15} />
      </button>
    </article>
  )
}
