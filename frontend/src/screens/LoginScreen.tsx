import { useState } from 'react'
import { Sparkles } from 'lucide-react'
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
    <div className="app-frame flex flex-col items-center justify-center px-8">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-accent-soft">
          <Sparkles size={36} className="text-accent" />
        </div>

        <h1 className="mt-6 text-3xl font-extrabold tracking-tight text-brand">소복소복</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-brand-dark/60">
          사장님께 딱 맞는 지원 정책을
          <br />
          AI가 찾아 알려드려요.
        </p>
      </div>

      <div className="mt-12 w-full">
        <button
          onClick={startGoogleLogin}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-2xl border border-black/10 bg-white py-3.5 text-base font-semibold text-brand-dark shadow-card active:scale-[0.99] disabled:opacity-60"
        >
          <GoogleMark />
          {loading ? '이동 중…' : 'Google로 시작하기'}
        </button>

        {error && (
          <p className="mt-4 text-center text-sm font-medium text-status-red">{error}</p>
        )}

        <p className="mt-6 text-center text-xs leading-relaxed text-brand-dark/40">
          로그인하면 저장한 정책이 계정에 보관되고,
          <br />
          마감일을 구글 캘린더에 등록할 수 있어요.
        </p>
      </div>
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
