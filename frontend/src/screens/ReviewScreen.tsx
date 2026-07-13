import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileText,
  Loader2,
  RotateCcw,
  Upload,
} from 'lucide-react'
import TopBar from '../components/TopBar'
import { apiFetch } from '../lib/api'
import { useSavedPolicies } from '../lib/storage'
import type { ReviewResponse, ReviewStartResponse, ReviewStatus } from '../types'

const POLL_INTERVAL_MS = 2500

// 정책을 고르면 policy_id가 넘어가고, 서버가 review_vectors와 요건을 대조한다.
// 고르지 않으면 그 단계를 통째로 건너뛰고 오타·빈칸 검사만 한다.
// 그래서 정책 선택을 기본값으로 두고, '정책 없이'는 명시적으로 고르게 한다.
const NO_POLICY = '__none__'

type Phase = 'idle' | 'running' | 'done'

/** 서버의 review_status를 화면의 3단계로 접는다. */
const STAGES = [
  { key: 'extract', label: '서류 읽는 중', statuses: ['queued', 'extracting'] },
  { key: 'match', label: '정책 요건 대조 중', statuses: ['matching'] },
  { key: 'diagnose', label: 'AI 진단 중', statuses: ['diagnosing'] },
] as const

export default function ReviewScreen() {
  const navigate = useNavigate()
  const location = useLocation()
  const { policies, loading: policiesLoading } = useSavedPolicies()

  // 정책 상세에서 넘어온 경우 드롭다운을 미리 채운다.
  const preselected = (location.state as { policyId?: string } | null)?.policyId
  const [policyId, setPolicyId] = useState<string>(preselected ?? '')
  const [file, setFile] = useState<File | null>(null)

  const [phase, setPhase] = useState<Phase>('idle')
  const [status, setStatus] = useState<ReviewStatus>('queued')
  const [hasMatching, setHasMatching] = useState(false)
  const [review, setReview] = useState<ReviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const timer = useRef<number | null>(null)

  // 저장한 정책이 로드되면 첫 정책을 기본 선택한다(정책 선택을 기본 경로로 만들기 위해).
  useEffect(() => {
    if (!policyId && !preselected && policies.length > 0) {
      setPolicyId(policies[0].policy_id)
    }
  }, [policies, policyId, preselected])

  useEffect(() => {
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [])

  const submit = async () => {
    if (!file) return
    setPhase('running')
    setStatus('queued')
    setError(null)
    setReview(null)

    try {
      const form = new FormData()
      form.append('file', file)
      if (policyId && policyId !== NO_POLICY) form.append('policy_id', policyId)

      // 파일 업로드는 FormData라 Content-Type을 브라우저가 정하게 둔다.
      const started = await apiFetch<ReviewStartResponse>('/api/v1/review', {
        method: 'POST',
        body: form,
      })
      setHasMatching(started.has_requirement_matching)
      poll(started.upload_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '검토 요청에 실패했습니다.')
      setPhase('idle')
    }
  }

  const poll = (uploadId: string) => {
    const tick = async () => {
      try {
        const data = await apiFetch<ReviewResponse>(`/api/v1/review/${uploadId}`)
        setStatus(data.review_status)

        if (data.review_status === 'done' || data.review_status === 'failed') {
          setReview(data)
          setPhase('done')
          return
        }
        timer.current = window.setTimeout(tick, POLL_INTERVAL_MS)
      } catch (e) {
        setError(e instanceof Error ? e.message : '검토 상태를 확인하지 못했습니다.')
        setPhase('idle')
      }
    }
    tick()
  }

  const reset = () => {
    if (timer.current) window.clearTimeout(timer.current)
    setPhase('idle')
    setFile(null)
    setReview(null)
    setError(null)
  }

  // 정책을 고르지 않았으면 '요건 대조' 단계가 없다. 있지도 않은 단계를 보여주면 거짓말이 된다.
  const stages = hasMatching ? STAGES : STAGES.filter((s) => s.key !== 'match')

  return (
    <div className="pb-6">
      <TopBar />

      <section className="px-5">
        <h2 className="text-2xl font-bold text-brand-dark">서류 검토</h2>
        <p className="mt-1 text-sm leading-relaxed text-brand-dark/55">
          제출 전에 오타·빈칸을 점검하고,
          <br />
          정책이 요구하는 서류가 빠지지 않았는지 확인해요.
        </p>
      </section>

      {phase === 'idle' && (
        <IdleForm
          policies={policies}
          policiesLoading={policiesLoading}
          policyId={policyId}
          onPolicyChange={setPolicyId}
          file={file}
          onFileChange={setFile}
          onSubmit={submit}
          error={error}
          onGoFind={() => navigate('/policies')}
        />
      )}

      {phase === 'running' && <Progress stages={stages} status={status} />}

      {phase === 'done' && review && <Result review={review} onReset={reset} />}
    </div>
  )
}

function IdleForm({
  policies,
  policiesLoading,
  policyId,
  onPolicyChange,
  file,
  onFileChange,
  onSubmit,
  error,
  onGoFind,
}: {
  policies: { policy_id: string; title: string }[]
  policiesLoading: boolean
  policyId: string
  onPolicyChange: (id: string) => void
  file: File | null
  onFileChange: (file: File | null) => void
  onSubmit: () => void
  error: string | null
  onGoFind: () => void
}) {
  const noSaved = !policiesLoading && policies.length === 0

  return (
    <>
      <section className="mt-6 px-5">
        <h3 className="text-sm font-bold text-brand-dark">
          <span className="mr-1.5 text-brand">①</span> 어떤 정책에 낼 서류인가요?
        </h3>

        {noSaved ? (
          <div className="mt-3 rounded-2xl bg-white p-4 shadow-card">
            <p className="text-sm leading-relaxed text-brand-dark/60">
              저장한 정책이 없어요. 정책을 저장하면 그 정책이 요구하는 서류가
              빠지지 않았는지도 함께 확인해드려요.
            </p>
            <button
              onClick={onGoFind}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-dark py-2.5 text-sm font-bold text-white"
            >
              정책 찾으러 가기 <ArrowRight size={15} />
            </button>
          </div>
        ) : (
          <select
            value={policyId}
            onChange={(e) => onPolicyChange(e.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white px-4 py-3.5 text-sm font-semibold text-brand-dark shadow-card"
          >
            {policiesLoading && <option>불러오는 중…</option>}
            {policies.map((p) => (
              <option key={p.policy_id} value={p.policy_id}>
                {p.title}
              </option>
            ))}
            <option value={NO_POLICY}>정책 없이 서류만 검토할게요</option>
          </select>
        )}

        {policyId === NO_POLICY && (
          <p className="mt-2 text-xs font-medium text-status-blue">
            정책 요건 대조는 건너뛰고 오타·빈칸·형식만 확인해요.
          </p>
        )}
      </section>

      <section className="mt-6 px-5">
        <h3 className="text-sm font-bold text-brand-dark">
          <span className="mr-1.5 text-brand">②</span> 서류를 올려주세요
        </h3>

        <label className="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-black/10 bg-white py-10 shadow-card active:bg-black/[0.02]">
          <input
            type="file"
            accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.xls"
            className="hidden"
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <>
              <FileText size={30} className="text-brand" />
              <p className="mt-3 max-w-[240px] truncate px-4 text-sm font-bold text-brand-dark">
                {file.name}
              </p>
              <p className="mt-1 text-xs text-brand-dark/45">다른 파일을 고르려면 눌러주세요</p>
            </>
          ) : (
            <>
              <Upload size={30} className="text-brand-dark/30" />
              <p className="mt-3 text-sm font-bold text-brand-dark/70">파일 선택</p>
              <p className="mt-1 text-xs text-brand-dark/40">PDF · HWP · DOCX · XLSX</p>
            </>
          )}
        </label>

        {error && <p className="mt-3 text-sm font-medium text-status-red">{error}</p>}

        <button
          onClick={onSubmit}
          disabled={!file}
          className="mt-5 w-full rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-dark/20 active:scale-[0.99] disabled:bg-brand-dark/30 disabled:shadow-none"
        >
          검토 시작하기
        </button>
      </section>
    </>
  )
}

function Progress({
  stages,
  status,
}: {
  stages: readonly { key: string; label: string; statuses: readonly string[] }[]
  status: ReviewStatus
}) {
  const activeIndex = stages.findIndex((s) => s.statuses.includes(status))

  return (
    <section className="mt-8 px-5">
      <div className="rounded-3xl bg-white p-6 shadow-card">
        <div className="space-y-5">
          {stages.map((stage, i) => {
            const done = activeIndex > i
            const active = activeIndex === i
            return (
              <div key={stage.key} className="flex items-center gap-3">
                <span
                  className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${
                    done
                      ? 'bg-green-50 text-status-green'
                      : active
                        ? 'bg-accent-soft text-accent'
                        : 'bg-black/[0.04] text-brand-dark/25'
                  }`}
                >
                  {done ? (
                    <Check size={18} strokeWidth={3} />
                  ) : active ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <span className="text-sm font-bold">{i + 1}</span>
                  )}
                </span>
                <span
                  className={`text-sm font-bold ${
                    done
                      ? 'text-brand-dark/40'
                      : active
                        ? 'text-brand-dark'
                        : 'text-brand-dark/30'
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>

        <p className="mt-6 border-t border-black/5 pt-4 text-xs leading-relaxed text-brand-dark/45">
          AI 진단은 1분 정도 걸릴 수 있어요.
          <br />
          이 화면을 벗어나도 검토는 계속 진행돼요.
        </p>
      </div>
    </section>
  )
}

function Result({ review, onReset }: { review: ReviewResponse; onReset: () => void }) {
  const failed = review.review_status === 'failed'
  const result = review.result

  if (failed || !result) {
    return (
      <section className="mt-8 px-5">
        <div className="rounded-3xl bg-white p-6 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50">
            <AlertTriangle size={22} className="text-status-red" />
          </div>
          <h3 className="mt-4 text-lg font-bold text-brand-dark">검토하지 못했어요</h3>
          <p className="mt-2 text-sm leading-relaxed text-brand-dark/60">
            {result?.overall || '서류를 읽는 데 실패했습니다.'}
          </p>
          <button
            onClick={onReset}
            className="mt-5 flex w-full items-center justify-center gap-1.5 rounded-2xl bg-brand-dark py-3 text-sm font-bold text-white"
          >
            <RotateCcw size={15} /> 다시 검토하기
          </button>
        </div>
      </section>
    )
  }

  const missingDocs = result.missing_documents

  return (
    <section className="mt-6 space-y-4 px-5">
      {/* 종합 진단 */}
      <div className="rounded-3xl bg-gradient-to-br from-accent-soft to-[#FBD9A8] p-5">
        <p className="text-xs font-bold text-brand-dark/60">{result.document_type}</p>
        <p className="mt-2 text-[15px] font-semibold leading-relaxed text-brand-dark">
          {result.overall}
        </p>
      </div>

      <FindingList
        title="오타·맞춤법"
        items={result.typos}
        emptyLabel="발견된 오타가 없어요."
        tone="warn"
      />
      <FindingList
        title="빠진 항목"
        items={result.missing_fields}
        emptyLabel="빈칸 없이 모두 작성되었어요."
        tone="warn"
      />
      <FindingList
        title="형식 오류"
        items={result.format_issues}
        emptyLabel="형식 문제가 없어요."
        tone="warn"
      />

      {/* 요건 대조는 정책을 골랐을 때만 의미가 있다 */}
      {review.policy_id && (
        <FindingList
          title="따로 제출해야 할 서류"
          items={missingDocs}
          emptyLabel="필요한 서류가 모두 준비된 것 같아요."
          tone="doc"
        />
      )}

      <FindingList
        title="보완하면 좋은 점"
        items={result.improvement_points}
        emptyLabel="특별히 보완할 점이 없어요."
        tone="info"
      />

      <button
        onClick={onReset}
        className="flex w-full items-center justify-center gap-1.5 rounded-2xl border border-black/10 bg-white py-3 text-sm font-bold text-brand-dark shadow-card"
      >
        <RotateCcw size={15} /> 다른 서류 검토하기
      </button>
    </section>
  )
}

function FindingList({
  title,
  items,
  emptyLabel,
  tone,
}: {
  title: string
  items: string[]
  emptyLabel: string
  tone: 'warn' | 'doc' | 'info'
}) {
  const empty = items.length === 0
  const badge =
    tone === 'warn'
      ? 'bg-red-50 text-status-red'
      : tone === 'doc'
        ? 'bg-blue-50 text-status-blue'
        : 'bg-brand-light/20 text-brand'

  return (
    <div className="rounded-2xl bg-white p-4 shadow-card">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-bold text-brand-dark">{title}</h4>
        {empty ? (
          <span className="rounded-lg bg-green-50 px-2 py-0.5 text-xs font-bold text-status-green">
            문제 없음
          </span>
        ) : (
          <span className={`rounded-lg px-2 py-0.5 text-xs font-bold ${badge}`}>
            {items.length}건
          </span>
        )}
      </div>

      {empty ? (
        <p className="mt-2 text-sm text-brand-dark/45">{emptyLabel}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item, i) => (
            <li
              key={`${item}-${i}`}
              className="flex gap-2 text-sm leading-relaxed text-brand-dark/75"
            >
              <span className="mt-[7px] h-1 w-1 flex-shrink-0 rounded-full bg-brand-dark/30" />
              <span className="min-w-0 break-words">{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
