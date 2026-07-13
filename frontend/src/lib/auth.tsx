import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiFetch, clearToken, getToken, setToken, UnauthorizedError } from './api'
import type { UserMe } from '../types'

interface AuthState {
  /** 로딩 중에는 라우팅 판단을 미뤄야 한다. 안 그러면 로그인된 사용자가 로그인 화면을 한 번 보고 지나간다. */
  loading: boolean
  user: UserMe | null
  /** 온보딩 완료 여부. 서버의 onboarded_at으로 판정한다. */
  onboarded: boolean
  login: (token: string) => Promise<void>
  logout: () => void
  /** 온보딩을 막 마쳤을 때 호출. 서버를 다시 묻지 않고 상태만 갱신한다. */
  markOnboarded: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState<UserMe | null>(null)

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(await apiFetch<UserMe>('/api/v1/users/me'))
    } catch (error) {
      // 401이면 apiFetch가 이미 토큰을 버렸다. 그 외 오류(서버 다운 등)도
      // 로그인 상태를 확신할 수 없으니 로그아웃으로 취급한다.
      if (!(error instanceof UnauthorizedError)) clearToken()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  const login = useCallback(
    async (token: string) => {
      setToken(token)
      setLoading(true)
      await loadMe()
    },
    [loadMe],
  )

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const markOnboarded = useCallback(() => {
    setUser((prev) => (prev ? { ...prev, onboarded: true } : prev))
  }, [])

  return (
    <AuthContext.Provider
      value={{
        loading,
        user,
        onboarded: Boolean(user?.onboarded),
        login,
        logout,
        markOnboarded,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
