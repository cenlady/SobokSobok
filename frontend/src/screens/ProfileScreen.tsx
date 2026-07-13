import {
  Bell,
  CalendarSync,
  ChevronRight,
  Lock,
  MapPin,
  Pencil,
  SlidersHorizontal,
  Users,
  Utensils,
  Wallet,
  CheckCircle2,
  BriefcaseBusiness,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { useProfile } from '../lib/storage'
import { useState, useEffect } from 'react'
import { NEED_OPTIONS } from '../lib/recommend'

export default function ProfileScreen() {
  const navigate = useNavigate()
  const { profile } = useProfile()
  const [alarm, setAlarm] = useState(true)

  // 구글 로그인 세션 상태 관리 (로컬스토리지 바인딩)
  const [token, setToken] = useState<string | null>(localStorage.getItem('google_access_token'))
  const [email, setEmail] = useState<string | null>(localStorage.getItem('user_email'))

  // 1) 구글 로그인 성공 후 리다이렉션으로 넘어온 토큰 및 이메일 감지/저장
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlToken = params.get('token')
    const urlEmail = params.get('email')

    if (urlToken && urlEmail) {
      localStorage.setItem('google_access_token', urlToken)
      localStorage.setItem('user_email', urlEmail)
      setToken(urlToken)
      setEmail(urlEmail)
      
      // 주소창의 지저분한 토큰 파라미터 지우기 (세탁)
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [])

  // 2) 구글 로그인 리다이렉션 링크 획득 및 이동 핸들러
  const handleGoogleLogin = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/google/login-url')
      if (!response.ok) throw new Error('Backend error')
      const data = await response.json()
      if (data.login_url) {
        window.location.href = data.login_url // 구글 동의 페이지로 리다이렉션
      }
    } catch (err) {
      alert('구글 로그인 URL을 가져오는 데 실패했습니다. 백엔드가 켜져 있는지 확인하세요.')
    }
  }

  // 3) 로그아웃 핸들러
  const handleLogout = () => {
    localStorage.removeItem('google_access_token')
    localStorage.removeItem('user_email')
    setToken(null)
    setEmail(null)
    alert('로그아웃되었습니다.')
  }

  // A. 로그인이 되어 있지 않은 대기 상태 (구글 로그인 유도 컴포넌트 렌더링)
  if (!token) {
    return (
      <div className="flex min-h-screen flex-col bg-cream pb-8">
        <TopBar />
        <div className="flex flex-1 flex-col items-center justify-center px-6 py-16">
          {/* 모던 애니메이션 아이콘 */}
          <div className="relative flex h-28 w-28 items-center justify-center rounded-full bg-brand-light/20 text-5xl animate-pulse">
            👋
            <span className="absolute -right-1 -top-1 flex h-4 w-4">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75"></span>
              <span className="relative inline-flex h-4 w-4 rounded-full bg-brand"></span>
            </span>
          </div>

          <h2 className="mt-8 text-center text-2xl font-extrabold tracking-tight text-brand-dark">
            사장님, 반갑습니다!
          </h2>
          <p className="mt-3 text-center text-sm leading-relaxed text-brand-dark/70 max-w-xs">
            구글 소셜 로그인을 완료하고 사장님만의 맞춤 지원사업 정보와 캘린더 연동 알림을 시작해 보세요.
          </p>

          {/* 구글 공식 브랜드 가이드라인 적용 모던 버튼 */}
          <button
            onClick={handleGoogleLogin}
            className="mt-10 flex w-full max-w-sm items-center justify-center gap-3 rounded-2xl bg-white px-5 py-4 text-base font-bold text-brand-dark shadow-card hover:bg-neutral-50 transition-transform active:scale-[0.98] border border-black/5"
          >
            {/* 구글 SVG 로고 */}
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l3.66-2.85z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.85c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Google 계정으로 로그인
          </button>

          <p className="mt-4 text-xs text-brand-dark/40">
            구글 보안 로그인 연동을 통해 사장님의 개인정보를 안전하게 매핑합니다.
          </p>
        </div>
      </div>
    )
  }

  // B. 구글 로그인 인증이 완료된 상태 (사장님 프로필 대시보드 렌더링)
  return (
    <div className="pb-8 bg-cream min-h-screen">
      <TopBar />

      {/* 프로필 헤더 */}
      <section className="flex flex-col items-center px-5 pt-2">
        <div className="relative">
          <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full bg-brand-light/30 text-3xl">
            👩‍🍳
          </div>
          <button className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-brand-dark text-white ring-4 ring-cream">
            <Pencil size={14} />
          </button>
        </div>
        <h2 className="mt-3 text-2xl font-bold text-brand-dark">
          {profile.ownerName} 사장님
        </h2>
        
        {/* 로그인된 사용자 이메일 뱃지 노출 */}
        {email && (
          <p className="mt-0.5 text-xs text-brand/80 font-semibold bg-brand/5 px-2 py-0.5 rounded-full border border-brand/10">
            {email}
          </p>
        )}
        <p className="mt-1 text-sm text-brand-dark/50">{profile.storeName}</p>
      </section>

      {/* 사업장 정보 */}
      <section className="mt-6 px-5">
        <div className="flex items-start justify-between">
          <h3 className="text-lg font-bold text-brand-dark">맞춤 정책을 위한 사업장 정보</h3>
          <button
            onClick={() => navigate('/onboarding')}
            className="flex items-center whitespace-nowrap text-sm font-medium text-brand"
          >
            수정하기 <ChevronRight size={16} />
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <InfoTile icon={Utensils} label="업종" value={profile.industry} />
          <InfoTile icon={MapPin} label="지역" value={profile.region} />
          <InfoTile icon={BriefcaseBusiness} label="사업자 상태" value={profile.businessStatus} />
          <InfoTile icon={SlidersHorizontal} label="업력" value={profile.businessAge} />
        </div>
        <div className="mt-3">
          <InfoTile
            icon={Wallet}
            label="매출 규모"
            value={profile.revenue}
            badge="성장중"
            center
          />
        </div>
        <div className="mt-3">
          <InfoTile icon={Users} label="직원 수" value={profile.employees} />
        </div>
        {profile.needTags.length > 0 && (
          <p className="mt-3 rounded-2xl bg-white p-4 text-sm font-semibold text-brand-dark shadow-card">
            관심 지원: {profile.needTags.map((tag) => NEED_OPTIONS.find((item) => item.tag === tag)?.label || tag).join(', ')}
          </p>
        )}

        {/* 안내 배너 */}
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-green-50 p-4">
          <CheckCircle2 size={26} className="flex-shrink-0 text-status-green" />
          <p className="text-sm text-brand-dark">
            <span className="font-bold">12개의 새로운 정책이 사장님을 기다려요!</span>
            <br />
            <span className="text-brand-dark/60">
              정보가 최신일수록 더 정확한 추천이 가능합니다.
            </span>
          </p>
        </div>
      </section>

      {/* 설정 및 관리 */}
      <section className="mt-8 px-5">
        <h3 className="text-lg font-bold text-brand-dark">설정 및 관리</h3>
        <div className="mt-4 divide-y divide-black/5 overflow-hidden rounded-2xl bg-white shadow-card">
          <div className="flex items-center gap-3 p-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
              <Bell size={20} className="text-status-blue" />
            </span>
            <span className="flex-1">
              <span className="block font-semibold text-brand-dark">알림 설정</span>
              <span className="block text-xs text-brand-dark/50">지원금 소식 및 마감 알림</span>
            </span>
            <button
              onClick={() => setAlarm((v) => !v)}
              className={`relative h-7 w-12 rounded-full transition-colors ${
                alarm ? 'bg-brand-dark' : 'bg-brand-dark/20'
              }`}
            >
              <span
                className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${
                  alarm ? 'left-6' : 'left-1'
                }`}
              />
            </button>
          </div>

          <SettingRow icon={CalendarSync} iconBg="bg-accent-soft" iconColor="text-accent" title="캘린더 연동 관리" desc="구글/애플 캘린더 자동 동기화" />
          <SettingRow icon={Lock} iconBg="bg-black/5" iconColor="text-brand-dark/60" title="로그인 및 보안" desc="비밀번호 변경 및 기기 관리" />
        </div>

        {/* 로그아웃 및 회원 관리 버튼 */}
        <div className="mt-8 flex flex-col items-center gap-3">
          <button
            onClick={handleLogout}
            className="text-sm font-medium text-brand-dark/50 hover:text-brand transition-colors cursor-pointer"
          >
            로그아웃
          </button>
          <button className="text-sm font-medium text-status-red hover:underline cursor-pointer">
            탈퇴하기
          </button>
        </div>
      </section>
    </div>
  )
}

function InfoTile({
  icon: Icon,
  label,
  value,
  badge,
  center,
}: {
  icon: typeof MapPin
  label: string
  value: string
  badge?: string
  center?: boolean
}) {
  return (
    <div className={`rounded-2xl bg-white p-4 shadow-card ${center ? 'text-center' : ''}`}>
      <Icon
        size={22}
        className={`text-brand ${center ? 'mx-auto' : ''}`}
      />
      <p className="mt-3 text-xs text-brand-dark/50">{label}</p>
      <p className="mt-0.5 flex items-center gap-2 text-base font-bold text-brand-dark">
        {center && <span className="flex-1" />}
        {value}
        {badge && (
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-status-green">
            {badge}
          </span>
        )}
        {center && <span className="flex-1" />}
      </p>
    </div>
  )
}

function SettingRow({
  icon: Icon,
  iconBg,
  iconColor,
  title,
  desc,
}: {
  icon: typeof MapPin
  iconBg: string
  iconColor: string
  title: string
  desc: string
}) {
  return (
    <button className="flex w-full items-center gap-3 p-4 text-left active:bg-black/[0.02]">
      <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
        <Icon size={20} className={iconColor} />
      </span>
      <span className="flex-1">
        <span className="block font-semibold text-brand-dark">{title}</span>
        <span className="block text-xs text-brand-dark/50">{desc}</span>
      </span>
      <ChevronRight size={20} className="text-brand-dark/30" />
    </button>
  )
}
