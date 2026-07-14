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
        <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-line border-t-primary" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  // 온보딩을 안 마쳤으면 어디를 가려 하든 온보딩으로 보낸다.
  // 반대로, 마친 뒤에도 /onboarding에는 들어갈 수 있어야 한다 — 마이페이지의 '수정하기'가
  // 그리로 보내기 때문. 막아두면 프로필을 영영 못 고치고 추천도 영영 그대로가 된다.
  if (!onboarded && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
