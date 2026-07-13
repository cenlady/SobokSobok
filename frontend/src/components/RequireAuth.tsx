import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

/**
 * 로그인·온보딩 가드.
 *
 *   미로그인        → /login
 *   로그인 + 미온보딩 → /onboarding   (추천이 프로필에 전적으로 의존하므로 건너뛸 수 없다)
 *   로그인 + 온보딩   → 통과
 *
 * loading 중에 판단하면 이미 로그인한 사용자가 로그인 화면을 한 번 스쳐 지나간다.
 * 그래서 확인이 끝날 때까지 아무 데도 보내지 않는다.
 */
export default function RequireAuth() {
  const { loading, user, onboarded } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="app-frame flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-black/10 border-t-brand" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  const isOnboarding = location.pathname === '/onboarding'
  if (!onboarded && !isOnboarding) {
    return <Navigate to="/onboarding" replace />
  }
  // 온보딩을 이미 마쳤는데 /onboarding에 남아 있으면 홈으로 돌려보낸다.
  if (onboarded && isOnboarding) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
