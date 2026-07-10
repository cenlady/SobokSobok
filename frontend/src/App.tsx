import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import HomeScreen from './screens/HomeScreen'
import CalendarScreen from './screens/CalendarScreen'
import ChatScreen from './screens/ChatScreen'
import ProfileScreen from './screens/ProfileScreen'
import OnboardingScreen from './screens/OnboardingScreen'
import BenefitDetailScreen from './screens/BenefitDetailScreen'
import PolicyDetailScreen from './screens/PolicyDetailScreen'

export default function App() {
  return (
    <Routes>
      {/* 하단 탭이 있는 화면 */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomeScreen />} />
        <Route path="/calendar" element={<CalendarScreen />} />
        <Route path="/chat" element={<ChatScreen />} />
        <Route path="/profile" element={<ProfileScreen />} />
      </Route>

      {/* 전체 화면 (탭 없음) */}
      <Route path="/onboarding" element={<OnboardingScreen />} />
      <Route path="/benefit/:id" element={<BenefitDetailScreen />} />
      <Route path="/policy/:policyId" element={<PolicyDetailScreen />} />
    </Routes>
  )
}
