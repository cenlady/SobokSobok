import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ExternalLink,
  FileText,
  Info,
  Loader2,
  Plus,
  RotateCcw,
  Upload,
  X,
} from 'lucide-react'
import TopBar from '../components/TopBar'
import { Button, EmptyState } from '../components/ui'
import { apiFetch } from '../lib/api'
import { useSavedPolicies } from '../lib/storage'
import type {
  RequirementMatch,
  ReviewFile,
  ReviewResponse,
  ReviewStartResponse,
  ReviewStatus,
} from '../types'

const POLL_INTERVAL_MS = 2500
const MAX_FILES = 10

// 정책을 고르면 policy_id가 넘어가고, 서버가 요건과 대조한다.
// 고르지 않으면 그 단계를 건너뛰고 오타·빈칸 검사만 한다.
// 그래서 정책 선택을 기본값으로 두고, '정책 없이'는 명시적으로 고르게 한다.
const NO_POLICY = '__none__'

// 검토는 서버에서 도는데 session_id를 컴포넌트 state에만 두면, 탭을 옮기는 순간
// 돌아올 길이 사라진다. 진행 중인 검토를 찾아갈 수 있게 id를 남겨둔다.
const ACTIVE_REVIEW_KEY = 'sobok.activeReview'

interface ActiveReview {
  sessionId: string
  hasMatching: boolean
}

function readActive(): ActiveReview | null {
  try {
    const raw = localStorage.getItem(ACTIVE_REVIEW_KEY)
    return raw ? (JSON.parse(raw) as ActiveReview) : null
  } catch {
    return null
  }
}

function writeActive(value: ActiveReview | null) {
  try {
    if (value) localStorage.setItem(ACTIVE_REVIEW_KEY, JSON.stringify(value))
    else localStorage.removeItem(ACTIVE_REVIEW_KEY)
  } catch {
    // 저장에 실패해도 이번 화면에서는 폴링이 계속되므로 치명적이지 않다.
  }
}

type Phase = 'idle' | 'running' | 'done'

/** 서버의 review_status를 화면 단계로 접는다. 파이프라인 순서: 추출 → 진단 → 대조 */
const STAGES = [
  { key: 'extract', label: '서류 읽는 중', statuses: ['queued', 'extracting'] },
  { key: 'diagnose', label: 'AI가 서류 검토 중', statuses: ['diagnosing'] },
  { key: 'match', label: '정책 요건과 대조 중', statuses: ['matching'] },
] as const

export default function ReviewScreen() {
  const navigate = useNavigate()
  const location = useLocation()
  const { policies, loading: policiesLoading } = useSavedPolicies()

  const preselected = (location.state as { policyId?: string } | null)?.policyId
  const [policyId, setPolicyId] = useState<string>(preselected ?? '')
  const [files, setFiles] = useState<File[]>([])

  const restored = useRef(readActive())
  const [phase, setPhase] = useState<Phase>(restored.current ? 'running' : 'idle')
  const [status, setStatus] = useState<ReviewStatus>('queued')
  const [hasMatching, setHasMatching] = useState(restored.current?.hasMatching ?? false)
  const [review, setReview] = useState<ReviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const timer = useRef<number | null>(null)
  const alive = useRef(true)

  // 저장한 정책을 기본 선택한다 — 요건 대조를 기본 경로로 만들기 위해.
  useEffect(() => {
    if (!policyId && !preselected && policies.length > 0) {
      setPolicyId(policies[0].policy_id)
    }
  }, [policies, policyId, preselected])

  const poll = useCallback((sessionId: string) => {
    const tick = async () => {
      if (!alive.current) return
      try {
        const data = await apiFetch<ReviewResponse>(`/api/v1/review/${sessionId}`)
        if (!alive.current) return

        setStatus(data.review_status)

        if (data.review_status === 'done' || data.review_status === 'failed') {
          writeActive(null)
          setReview(data)
          setPhase('done')
          return
        }
        timer.current = window.setTimeout(tick, POLL_INTERVAL_MS)
      } catch (e) {
        if (!alive.current) return
        writeActive(null)
        setError(e instanceof Error ? e.message : '검토 상태를 확인하지 못했습니다.')
        setPhase('idle')
      }
    }
    tick()
  }, [])

  // 다른 탭에 다녀와도 진행 중이던 검토를 다시 붙잡는다.
  useEffect(() => {
    alive.current = true
    const active = restored.current
    if (active) poll(active.sessionId)

    return () => {
      alive.current = false
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [poll])

  const addFiles = (picked: FileList | null) => {
    if (!picked) return
    setFiles((prev) => {
      const merged = [...prev]
      for (const f of Array.from(picked)) {
        if (merged.length >= MAX_FILES) break
        // 같은 파일을 두 번 담지 않는다
        if (!merged.some((m) => m.name === f.name && m.size === f.size)) merged.push(f)
      }
      return merged
    })
  }

  const submit = async () => {
    if (files.length === 0) return
    setPhase('running')
    setStatus('queued')
    setError(null)
    setReview(null)

    try {
      const form = new FormData()
      for (const f of files) form.append('files', f)
      if (policyId && policyId !== NO_POLICY) form.append('policy_id', policyId)

      const started = await apiFetch<ReviewStartResponse>('/api/v1/review', {
        method: 'POST',
        body: form,
      })
      setHasMatching(started.has_requirement_matching)
      writeActive({
        sessionId: started.session_id,
        hasMatching: started.has_requirement_matching,
      })
      poll(started.session_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '검토 요청에 실패했습니다.')
      setPhase('idle')
    }
  }

  const reset = () => {
    if (timer.current) window.clearTimeout(timer.current)
    writeActive(null)
    restored.current = null
    setPhase('idle')
    setFiles([])
    setReview(null)
    setError(null)
  }

  // 요건 대조를 안 하는 경우엔 그 단계를 보여주지 않는다. 없는 단계를 보여주면 거짓말이다.
  const stages = hasMatching ? STAGES : STAGES.filter((s) => s.key !== 'match')

  return (
    <div className="pb-6">
      <TopBar />

      <section className="px-5 pt-2">
        <h2 className="text-title text-ink">서류 검토</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted">
          제출 전에 오타·빈칸을 점검하고, 정책이 요구하는 서류가 빠지지 않았는지 확인해요.
        </p>
      </section>

      {phase === 'idle' && (
        <IdleForm
          policies={policies}
          policiesLoading={policiesLoading}
          policyId={policyId}
          onPolicyChange={setPolicyId}
          files={files}
          onAddFiles={addFiles}
          onRemoveFile={(i) => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
          onSubmit={submit}
          error={error}
          onGoFind={() => navigate('/policies')}
        />
      )}

      {phase === 'running' && <Progress stages={stages} status={status} count={files.length} />}

      {phase === 'done' && review && <Result review={review} onReset={reset} />}
    </div>
  )
}

/* ─────────────────────────── 입력 ─────────────────────────── */

function IdleForm({
  policies,
  policiesLoading,
  policyId,
  onPolicyChange,
  files,
  onAddFiles,
  onRemoveFile,
  onSubmit,
  error,
  onGoFind,
}: {
  policies: { policy_id: string; title: string }[]
  policiesLoading: boolean
  policyId: string
  onPolicyChange: (id: string) => void
  files: File[]
  onAddFiles: (files: FileList | null) => void
  onRemoveFile: (index: number) => void
  onSubmit: () => void
  error: string | null
  onGoFind: () => void
}) {
  const noSaved = !policiesLoading && policies.length === 0

  return (
    <>
      <section className="mt-6 px-5">
        <h3 className="text-sm font-bold text-ink">
          <span className="mr-1.5 text-primary">①</span> 어떤 정책에 낼 서류인가요?
        </h3>

        {noSaved ? (
          <div className="surface-panel mt-3 p-4">
            <p className="text-sm leading-relaxed text-muted">
              저장한 정책이 없어요. 정책을 저장하면 그 정책이 요구하는 서류가 빠지지 않았는지도
              함께 확인해드려요.
            </p>
            <Button onClick={onGoFind} size="sm" full className="mt-3">
              정책 찾으러 가기 <ArrowRight size={14} />
            </Button>
          </div>
        ) : (
          <select
            value={policyId}
            onChange={(e) => onPolicyChange(e.target.value)}
            className="mt-3 h-12 w-full rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink"
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
          <p className="mt-2 text-xs font-medium text-muted">
            정책 요건 대조는 건너뛰고 오타·빈칸·형식만 확인해요.
          </p>
        )}
      </section>

      <section className="mt-6 px-5">
        <h3 className="text-sm font-bold text-ink">
          <span className="mr-1.5 text-primary">②</span> 준비한 서류를 모두 올려주세요
        </h3>
        {/* 파일을 하나만 받으면 "사업자등록증 하나 올렸더니 24개가 누락됐다"는,
            맞지만 쓸모없는 결과가 나온다. 준비한 것을 다 올려야 무엇이 빠졌는지가 정보가 된다. */}
        <p className="mt-1 text-xs text-muted">
          여러 개를 한 번에 올리면 무엇이 빠졌는지 정확히 알려드려요. (최대 {MAX_FILES}개)
        </p>

        {files.length === 0 ? (
          <label className="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-line bg-surface py-10 transition-colors hover:bg-cream/60">
            <input
              type="file"
              multiple
              accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.xls"
              className="hidden"
              onChange={(e) => onAddFiles(e.target.files)}
            />
            <Upload size={28} strokeWidth={1.6} className="text-faint" />
            <p className="mt-3 text-sm font-bold text-ink">파일 선택</p>
            <p className="mt-1 text-xs text-subtle">PDF · HWP · DOCX · XLSX</p>
          </label>
        ) : (
          <div className="mt-3 space-y-2">
            <div className="surface-panel divide-y divide-line overflow-hidden">
              {files.map((file, i) => (
                <div key={`${file.name}-${i}`} className="flex items-center gap-3 px-4 py-3">
                  <FileText size={17} strokeWidth={1.8} className="shrink-0 text-brand" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink">{file.name}</span>
                    <span className="block text-xs text-subtle">
                      {(file.size / 1024).toFixed(0)} KB
                    </span>
                  </span>
                  <button
                    onClick={() => onRemoveFile(i)}
                    aria-label={`${file.name} 제거`}
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-subtle transition-colors hover:text-ink active:bg-line/50"
                  >
                    <X size={17} />
                  </button>
                </div>
              ))}
            </div>

            {files.length < MAX_FILES && (
              <label className="flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-xl border border-dashed border-line text-sm font-semibold text-muted transition-colors hover:bg-cream/60">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.xls"
                  className="hidden"
                  onChange={(e) => onAddFiles(e.target.files)}
                />
                <Plus size={15} /> 서류 더 추가
              </label>
            )}
          </div>
        )}

        {error && <p className="mt-3 text-sm font-medium text-status-red">{error}</p>}

        <Button onClick={onSubmit} disabled={files.length === 0} full className="mt-5">
          {files.length > 0 ? `서류 ${files.length}건 검토 시작` : '검토 시작하기'}
        </Button>
      </section>
    </>
  )
}

/* ─────────────────────────── 진행 ─────────────────────────── */

function Progress({
  stages,
  status,
  count,
}: {
  stages: readonly { key: string; label: string; statuses: readonly string[] }[]
  status: ReviewStatus
  count: number
}) {
  const activeIndex = stages.findIndex((s) => s.statuses.includes(status))

  return (
    <section className="mt-8 px-5">
      <div className="surface-panel p-6">
        <div className="space-y-5">
          {stages.map((stage, i) => {
            const done = activeIndex > i
            const active = activeIndex === i
            return (
              <div key={stage.key} className="flex items-center gap-3">
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                    done
                      ? 'bg-status-green/10 text-status-green'
                      : active
                        ? 'bg-primary-soft text-primary'
                        : 'bg-line/60 text-faint'
                  }`}
                >
                  {done ? (
                    <Check size={17} strokeWidth={3} />
                  ) : active ? (
                    <Loader2 size={17} className="animate-spin" />
                  ) : (
                    <span className="text-sm font-bold">{i + 1}</span>
                  )}
                </span>
                <span
                  className={`text-sm font-bold ${
                    done ? 'text-subtle' : active ? 'text-ink' : 'text-faint'
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>

        <p className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-muted">
          서류 {count}건을 하나씩 읽고 있어요. 1~2분 정도 걸릴 수 있어요.
          <br />이 화면을 벗어나도 검토는 계속돼요.
        </p>
      </div>
    </section>
  )
}

/* ─────────────────────────── 결과 ─────────────────────────── */

function Result({ review, onReset }: { review: ReviewResponse; onReset: () => void }) {
  const failed = review.review_status === 'failed'
  const readable = review.files.filter((f) => f.diagnosis)

  if (failed || readable.length === 0) {
    return (
      <section className="mt-8 px-5">
        <div className="surface-panel">
          <EmptyState
            icon={AlertTriangle}
            title="검토하지 못했어요"
            description={review.summary || '서류를 읽는 데 실패했습니다.'}
            actionLabel="다시 검토하기"
            onAction={onReset}
          />
        </div>
      </section>
    )
  }

  return (
    <section className="mt-6 space-y-5 px-5">
      {review.summary && (
        <div className="rounded-2xl bg-primary-soft p-4">
          <p className="text-[15px] font-semibold leading-relaxed text-ink">{review.summary}</p>
        </div>
      )}

      {/* '요건이 없다'와 '요건을 충족했다'를 절대 뭉뚱그리지 않는다 */}
      <RequirementSection review={review} />

      <div>
        <h3 className="text-section text-ink">서류별 검토</h3>
        <div className="mt-3 space-y-3">
          {review.files.map((file) => (
            <FileResult key={file.upload_id} file={file} />
          ))}
        </div>
      </div>

      <Button variant="secondary" full onClick={onReset}>
        <RotateCcw size={15} /> 다른 서류 검토하기
      </Button>
    </section>
  )
}

function RequirementSection({ review }: { review: ReviewResponse }) {
  const { requirement_status, requirement_matches } = review

  if (requirement_status === 'not_requested') return null

  // 이 정책은 공고에 필수서류가 명시돼 있지 않다(전체의 63%).
  // 대조를 못 했다는 사실을 숨기고 "모두 준비됐다"고 하면 근거 없는 안심이 된다.
  if (requirement_status === 'no_requirement_data') {
    return (
      <div className="surface-panel p-4">
        <div className="flex items-start gap-2.5">
          <Info size={17} strokeWidth={1.8} className="mt-0.5 shrink-0 text-subtle" />
          <div>
            <p className="text-sm font-semibold text-ink">요건 대조는 하지 못했어요</p>
            <p className="mt-1 text-sm leading-relaxed text-muted">
              이 정책은 공고에 필수 서류가 명시되어 있지 않아요. 서류 자체 검토 결과만
              확인해주세요.
            </p>
          </div>
        </div>
      </div>
    )
  }

  const covered = requirement_matches.filter((m) => m.likely_covered)
  const missing = requirement_matches.filter((m) => !m.likely_covered)

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="text-section text-ink">정책 요건 대조</h3>
        <span className="text-sm font-bold text-ink">
          {covered.length}
          <span className="text-subtle"> / {requirement_matches.length}</span>
        </span>
      </div>

      <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
        {[...covered, ...missing].map((m) => (
          <RequirementRow key={m.document_name} match={m} />
        ))}
      </div>

      {missing.length > 0 && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted">
          아직 없는 서류를 누르면 어디서 어떻게 발급받는지 알려드려요.
        </p>
      )}
    </div>
  )
}

/**
 * 요건 한 줄. 아직 없는 서류는 눌러서 '어디서 어떻게 떼는지' 펼쳐 볼 수 있다.
 *
 * 이미 낸 서류에는 가이드를 붙이지 않는다. 이미 가진 것을 어떻게 발급받는지는
 * 알려줄 필요가 없다.
 */
function RequirementRow({ match }: { match: RequirementMatch }) {
  const [open, setOpen] = useState(false)
  const guide = !match.likely_covered ? match.guide : null

  const body = (
    <div className="flex items-center gap-3">
      <span
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
          match.likely_covered ? 'bg-status-green/10 text-status-green' : 'bg-line text-subtle'
        }`}
      >
        {match.likely_covered ? (
          <Check size={13} strokeWidth={3} />
        ) : (
          <X size={13} strokeWidth={2.5} />
        )}
      </span>

      <span className="min-w-0 flex-1 text-left">
        <span
          className={`block truncate text-sm ${
            match.likely_covered ? 'font-medium text-ink' : 'text-muted'
          }`}
        >
          {match.document_name}
        </span>
        {match.matched_file ? (
          <span className="mt-0.5 block truncate text-xs text-subtle">{match.matched_file}</span>
        ) : guide ? (
          <span className="mt-0.5 block truncate text-xs text-primary">
            {guide.issuer} · {guide.fee}
          </span>
        ) : null}
      </span>

      {guide && (
        <ChevronDown
          size={16}
          className={`shrink-0 text-subtle transition-transform ${open ? 'rotate-180' : ''}`}
        />
      )}
    </div>
  )

  if (!guide) {
    return <div className="px-4 py-3">{body}</div>
  }

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full px-4 py-3 transition-colors hover:bg-cream/60"
      >
        {body}
      </button>

      {open && (
        <div className="border-t border-line bg-cream/50 px-4 py-3 pl-13">
          <dl className="space-y-1.5 text-xs">
            {guide.online && (
              <div className="flex gap-2">
                <dt className="w-12 shrink-0 text-subtle">온라인</dt>
                <dd className="min-w-0 flex-1 text-ink">{guide.online}</dd>
              </div>
            )}
            {guide.offline && (
              <div className="flex gap-2">
                <dt className="w-12 shrink-0 text-subtle">방문</dt>
                <dd className="min-w-0 flex-1 text-ink">{guide.offline}</dd>
              </div>
            )}
            <div className="flex gap-2">
              <dt className="w-12 shrink-0 text-subtle">소요</dt>
              <dd className="min-w-0 flex-1 text-ink">
                {guide.duration} · {guide.fee}
              </dd>
            </div>
          </dl>

          {guide.tip && (
            <p className="mt-2.5 border-l-2 border-primary/30 pl-2.5 text-xs leading-relaxed text-muted">
              {guide.tip}
            </p>
          )}

          {guide.online_url && (
            <a
              href={guide.online_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex h-9 items-center gap-1 rounded-lg bg-primary px-3 text-xs font-bold text-white transition-colors hover:bg-primary-hover"
            >
              발급하러 가기 <ExternalLink size={12} />
            </a>
          )}
        </div>
      )}
    </div>
  )
}

function FileResult({ file }: { file: ReviewFile }) {
  const d = file.diagnosis

  if (!d) {
    const reason: Record<string, string> = {
      unsupported: '지원하지 않는 형식이에요',
      empty: '텍스트를 찾지 못했어요 (스캔 이미지일 수 있어요)',
      failed: '파일을 읽지 못했어요',
      pending: '아직 읽지 않았어요',
    }
    return (
      <div className="surface-panel flex items-center gap-3 p-4">
        <AlertTriangle size={17} strokeWidth={1.8} className="shrink-0 text-subtle" />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-ink">{file.file_name}</span>
          <span className="block text-xs text-muted">
            {reason[file.extraction_status] || '읽지 못했어요'}
          </span>
        </span>
      </div>
    )
  }

  const findings: { label: string; items: string[] }[] = [
    { label: '오타·맞춤법', items: d.typos },
    { label: '빠진 항목', items: d.missing_fields },
    { label: '형식 오류', items: d.format_issues },
    { label: '보완하면 좋은 점', items: d.improvement_points },
  ].filter((f) => f.items.length > 0)

  const issueCount = findings.reduce((n, f) => n + f.items.length, 0)

  return (
    <div className="surface-panel overflow-hidden">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <FileText size={17} strokeWidth={1.8} className="shrink-0 text-brand" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink">{file.file_name}</span>
          <span className="block text-xs text-subtle">{d.document_type}</span>
        </span>
        {issueCount === 0 ? (
          <span className="shrink-0 rounded-md bg-status-green/10 px-2 py-0.5 text-[11px] font-bold text-status-green">
            문제 없음
          </span>
        ) : (
          <span className="shrink-0 rounded-md bg-line px-2 py-0.5 text-[11px] font-bold text-muted">
            {issueCount}건
          </span>
        )}
      </div>

      <div className="px-4 py-3">
        <p className="text-sm leading-relaxed text-muted">{d.overall}</p>

        {findings.map((f) => (
          <div key={f.label} className="mt-3">
            <p className="text-xs font-bold text-ink">{f.label}</p>
            <ul className="mt-1 space-y-1">
              {f.items.map((item, i) => (
                <li key={`${item}-${i}`} className="flex gap-2 text-sm leading-relaxed text-muted">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-faint" />
                  <span className="min-w-0 break-words">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
