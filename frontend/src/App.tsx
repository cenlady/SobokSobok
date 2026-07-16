import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import RequireAuth from './components/RequireAuth'
import { AuthProvider } from './lib/auth'
import HomeScreen from './screens/HomeScreen'
import PolicySearchScreen from './screens/PolicySearchScreen'
import ReviewScreen from './screens/ReviewScreen'
import ChatScreen from './screens/ChatScreen'
import ProfileScreen from './screens/ProfileScreen'
import OnboardingScreen from './screens/OnboardingScreen'
import PolicyDetailScreen from './screens/PolicyDetailScreen'
import LoginScreen from './screens/LoginScreen'
import AuthCallbackScreen from './screens/AuthCallbackScreen'
import AiSettingsScreen from './screens/AiSettingsScreen'
import WelcomeScreen from './screens/WelcomeScreen'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* 인증 전 (가드 밖) */}
        <Route path="/login" element={<LoginScreen />} />
        <Route path="/auth/callback" element={<AuthCallbackScreen />} />

        {/* 이하 전부 로그인 필수. 온보딩을 안 마쳤으면 /onboarding으로 보낸다. */}
        <Route element={<RequireAuth />}>
          {/* 온보딩·환영은 하단 탭 없이 전체 화면 */}
          <Route path="/onboarding" element={<OnboardingScreen />} />
          <Route path="/welcome" element={<WelcomeScreen />} />

          {/* 하단 탭이 있는 화면 */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/policies" element={<PolicySearchScreen />} />
            <Route path="/review" element={<ReviewScreen />} />
            <Route path="/chat" element={<ChatScreen />} />
            <Route path="/profile" element={<ProfileScreen />} />
          </Route>

          {/* 상세는 탭 없이 전체 화면 */}
          <Route path="/policy/:policyId" element={<PolicyDetailScreen />} />
          <Route path="/profile/ai-settings" element={<AiSettingsScreen />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
