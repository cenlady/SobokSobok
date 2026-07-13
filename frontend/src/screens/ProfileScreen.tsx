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
import { useAuth } from '../lib/auth'
import { useProfile } from '../lib/storage'
import { useState } from 'react'
import { NEED_OPTIONS } from '../lib/recommend'

export default function ProfileScreen() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { profile } = useProfile()
  const [alarm, setAlarm] = useState(true)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

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
        {user?.email && (
          <p className="mt-0.5 text-xs text-brand/80 font-semibold bg-brand/5 px-2 py-0.5 rounded-full border border-brand/10">
            {user.email}
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
