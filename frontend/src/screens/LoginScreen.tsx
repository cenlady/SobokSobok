import { useState } from 'react'
import { CalendarDays, FileCheck2, Search } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function LoginScreen() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startGoogleLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      const { login_url } = await apiFetch<{ login_url: string }>(
        '/api/v1/auth/google/login-url',
        { anonymous: true },
      )
      window.location.href = login_url
    } catch {
      setError('로그인을 시작하지 못했습니다. 잠시 후 다시 시도해주세요.')
      setLoading(false)
    }
  }

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col justify-between px-6 pb-8 pt-7">
      <div>
        <header className="flex items-center gap-2.5">
          <span className="grid h-7 w-7 grid-cols-2 gap-1" aria-hidden="true">
            <span className="rounded-[3px] bg-brand" />
            <span className="rounded-[3px] bg-accent/70" />
            <span className="rounded-[3px] bg-brand-light" />
            <span className="rounded-[3px] bg-brand-dark" />
          </span>
          <span className="text-xl font-bold tracking-[-0.03em] text-brand-dark">소복소복</span>
        </header>

        <main className="pt-20">
          <p className="text-xs font-semibold tracking-[0.08em] text-brand">소상공인 정책 관리</p>
          <h1 className="mt-3 text-[30px] font-bold leading-[1.28] tracking-[-0.04em] text-brand-dark">
            놓치기 쉬운 지원 정책을
            <br />
            한곳에서 관리하세요.
          </h1>
          <p className="mt-4 max-w-[320px] text-[15px] leading-relaxed text-muted">
            내 사업장 조건에 맞는 공고를 확인하고, 신청 마감과 준비 서류를 차근차근 챙길 수 있습니다.
          </p>

          <div className="mt-9 border-y border-line">
            <FeatureRow icon={Search} label="사업장 조건에 맞는 정책 확인" />
            <FeatureRow icon={CalendarDays} label="저장한 정책의 마감 일정 관리" />
            <FeatureRow icon={FileCheck2} label="제출 전 서류 내용 점검" />
          </div>
        </main>
      </div>

      <div className="pt-10">
        <button
          onClick={startGoogleLogin}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-line bg-surface py-3.5 text-[15px] font-semibold text-brand-dark active:bg-black/[0.025] disabled:opacity-50"
        >
          <GoogleMark />
          {loading ? '로그인 페이지로 이동 중…' : 'Google로 시작하기'}
        </button>

        {error && <p className="mt-3 text-sm font-medium text-status-red">{error}</p>}

        <p className="mt-4 text-xs leading-relaxed text-muted">
          로그인하면 저장한 정책을 계정에 보관하고 마감일을 Google Calendar에 등록할 수 있습니다.
        </p>
      </div>
    </div>
  )
}

function FeatureRow({ icon: Icon, label }: { icon: typeof Search; label: string }) {
  return (
    <div className="flex items-center gap-3 border-b border-line px-1 py-3.5 last:border-b-0">
      <Icon size={18} className="text-brand" />
      <span className="text-sm font-medium text-brand-dark/80">{label}</span>
    </div>
  )
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  )
}
