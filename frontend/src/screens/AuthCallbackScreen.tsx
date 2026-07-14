import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Notice } from '../components/ui'
import { useAuth } from '../lib/auth'

// 백엔드 콜백이 여기로 리다이렉트한다: /auth/callback?token=… 또는 ?error=…
// 토큰을 저장하고, 온보딩 여부에 따라 목적지를 정한다.

const ERROR_MESSAGES: Record<string, string> = {
  google_not_configured: '구글 로그인이 설정되지 않았습니다. 관리자에게 문의해주세요.',
  token_exchange_failed: '구글 인증에 실패했습니다. 다시 시도해주세요.',
  userinfo_failed: '구글 계정 정보를 가져오지 못했습니다. 다시 시도해주세요.',
}

export default function AuthCallbackScreen() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState<string | null>(null)

  // StrictMode가 effect를 두 번 실행하므로 로그인이 두 번 돌지 않게 막는다.
  const handled = useRef(false)

  useEffect(() => {
    if (handled.current) return
    handled.current = true

    const errorCode = params.get('error')
    if (errorCode) {
      setError(ERROR_MESSAGES[errorCode] || '로그인에 실패했습니다. 다시 시도해주세요.')
      return
    }

    const token = params.get('token')
    if (!token) {
      setError('로그인 정보를 받지 못했습니다. 다시 시도해주세요.')
      return
    }

    login(token)
      .then(() => {
        // 목적지 판단은 RequireAuth에 맡긴다. 여기서는 앱 안으로만 들여보낸다.
        navigate('/', { replace: true })
      })
      .catch(() => setError('로그인 처리 중 문제가 발생했습니다.'))
  }, [params, login, navigate])

  if (error) {
    return (
      <div className="app-frame flex items-center justify-center px-5">
        <Notice tone="error" className="w-full" title="로그인을 완료하지 못했습니다">
          <p>{error}</p>
          <Button
            onClick={() => navigate('/login', { replace: true })}
            variant="secondary"
            size="sm"
            className="mt-3"
          >
            로그인으로 돌아가기
          </Button>
        </Notice>
      </div>
    )
  }

  return (
    <div className="app-frame flex flex-col items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-line border-t-primary" />
      <p className="mt-4 text-sm font-medium text-muted">로그인 중이에요…</p>
    </div>
  )
}
