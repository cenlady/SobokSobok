import { useState } from 'react'
import { BookmarkCheck, CalendarCheck2 } from 'lucide-react'
import BrandMark from '../components/BrandMark'
import { Button, Notice } from '../components/ui'
import { apiFetch } from '../lib/api'

export default function LoginScreen() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startGoogleLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      // 로그인 URL 생성은 인증 전에 부르는 유일한 API라 anonymous로 호출한다.
      const { login_url } = await apiFetch<{ login_url: string }>(
        '/api/v1/auth/google/login-url',
        { anonymous: true },
      )
      // 구글 동의 → 백엔드 콜백 → /auth/callback?token=… 으로 돌아온다.
      window.location.href = login_url
    } catch {
      setError('로그인을 시작하지 못했습니다. 잠시 후 다시 시도해주세요.')
      setLoading(false)
    }
  }

  return (
    <main className="app-frame flex min-h-[100dvh] flex-col bg-cream px-5">
      <div className="flex flex-1 flex-col justify-center py-10">
        <section className="flex flex-col items-center text-center">
          <BrandMark size={72} />
          <p className="mt-3.5 text-[15px] font-extrabold tracking-[0.14em] text-brand">소복소복</p>

          <h1 className="mt-7 text-[27px] font-bold leading-[1.36] tracking-[-0.03em] text-ink">
            사장님에게 맞는
            <br />
            <span className="text-brand">지원 정책</span>을 찾아드려요
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-muted">
            흩어진 지원 공고를 사업장 조건과 비교해
            <br />
            신청할 만한 정책부터 보여드릴게요.
          </p>
        </section>

        <section className="mt-9">
          <Button
            onClick={startGoogleLogin}
            disabled={loading}
            variant="secondary"
            full
            className="gap-3 shadow-card"
          >
            {loading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-muted" />
            ) : (
              <GoogleMark />
            )}
            {loading ? 'Google로 이동 중…' : 'Google 계정으로 계속하기'}
          </Button>

          <div className="mt-4 grid grid-cols-2 divide-x divide-line rounded-xl border border-line bg-surface/70 py-3.5">
            <LoginBenefit icon={BookmarkCheck} label="맞춤 정책 저장" />
            <LoginBenefit icon={CalendarCheck2} label="마감일 일정 등록" />
          </div>

          {error && (
            <Notice tone="error" className="mt-3" title="로그인 연결이 원활하지 않아요">
              잠시 후 버튼을 다시 눌러주세요.
            </Notice>
          )}
        </section>
      </div>

      <p className="pb-7 text-center text-xs leading-relaxed text-subtle">
        로그인하면 저장한 정책을 어느 기기에서든
        <br />
        이어서 확인할 수 있어요.
      </p>
    </main>
  )
}

function LoginBenefit({
  icon: Icon,
  label,
}: {
  icon: typeof BookmarkCheck
  label: string
}) {
  return (
    <div className="flex items-center justify-center gap-2 px-2 text-xs font-semibold text-muted">
      <Icon size={16} strokeWidth={1.9} className="shrink-0 text-brand" />
      <span>{label}</span>
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
