import { useState } from 'react'
import {
  Bell,
  BriefcaseBusiness,
  CalendarSync,
  ChevronRight,
  Lock,
  MapPin,
  SlidersHorizontal,
  Users,
  Utensils,
  Wallet,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { useAuth } from '../lib/auth'
import { NEED_OPTIONS } from '../lib/recommend'
import { useProfile } from '../lib/storage'

export default function ProfileScreen() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { profile } = useProfile()
  const [alarm, setAlarm] = useState(true)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const ownerLabel = profile.ownerName || '사장님'
  const initial = ownerLabel.trim().slice(0, 1) || '사'
  const interestLabel = profile.needTags
    .map((tag) => NEED_OPTIONS.find((item) => item.tag === tag)?.label || tag)
    .join(', ')

  return (
    <div className="pb-8">
      <TopBar />

      <section className="px-5 pt-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-xl border border-line bg-surface text-xl font-bold text-brand">
            {initial}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-[0.08em] text-brand">내 사업장</p>
            <h2 className="mt-1 text-xl font-bold tracking-[-0.02em] text-brand-dark">
              {ownerLabel.includes('사장님') ? ownerLabel : `${ownerLabel} 사장님`}
            </h2>
            <p className="mt-1 truncate text-sm text-muted">{profile.storeName || '사업장 이름 미입력'}</p>
          </div>
        </div>
        {user?.email && <p className="mt-4 border-t border-line pt-3 text-xs text-muted">{user.email}</p>}
      </section>

      <section className="mt-8 px-5">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h3 className="section-title">사업장 정보</h3>
            <p className="mt-1 text-xs text-muted">정책 조건 확인에 사용하는 정보입니다.</p>
          </div>
          <button
            onClick={() => navigate('/onboarding')}
            className="flex items-center whitespace-nowrap text-xs font-semibold text-brand"
          >
            수정하기 <ChevronRight size={15} />
          </button>
        </div>

        <dl className="surface-panel mt-3 divide-y divide-line overflow-hidden">
          <InfoRow icon={Utensils} label="업종" value={profile.industry} />
          <InfoRow icon={MapPin} label="지역" value={profile.region} />
          <InfoRow icon={BriefcaseBusiness} label="사업자 상태" value={profile.businessStatus} />
          <InfoRow icon={SlidersHorizontal} label="업력" value={profile.businessAge} />
          <InfoRow icon={Wallet} label="매출 규모" value={profile.revenue} />
          <InfoRow icon={Users} label="직원 수" value={profile.employees} />
          {interestLabel && <InfoRow label="관심 지원" value={interestLabel} />}
        </dl>

        <p className="mt-3 border-l-2 border-status-green pl-3 text-xs leading-relaxed text-muted">
          사업장 정보가 최신일수록 조건이 맞는 정책을 더 정확하게 확인할 수 있습니다.
        </p>
      </section>

      <section className="mt-8 px-5">
        <h3 className="section-title">설정 및 관리</h3>
        <div className="surface-panel mt-3 divide-y divide-line overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3.5">
            <Bell size={18} className="text-brand" />
            <span className="flex-1">
              <span className="block text-sm font-medium text-brand-dark">마감 알림</span>
              <span className="mt-0.5 block text-xs text-muted">저장한 정책의 신청 마감 안내</span>
            </span>
            <button
              onClick={() => setAlarm((value) => !value)}
              role="switch"
              aria-checked={alarm}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                alarm ? 'bg-brand-dark' : 'bg-brand-dark/20'
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-all ${
                  alarm ? 'left-6' : 'left-1'
                }`}
              />
            </button>
          </div>

          <SettingRow
            icon={CalendarSync}
            title="Google Calendar"
            description="정책 마감일 일정 등록"
          />
          <SettingRow icon={Lock} title="로그인 및 보안" description="계정과 로그인 정보 관리" />
        </div>

        <div className="mt-8 border-t border-line pt-5">
          <button
            onClick={handleLogout}
            className="block text-sm font-medium text-brand-dark/60 active:opacity-60"
          >
            로그아웃
          </button>
          <button className="mt-4 block text-sm font-medium text-status-red">회원 탈퇴</button>
        </div>
      </section>
    </div>
  )
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon?: typeof MapPin
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-3 px-4 py-3.5">
      {Icon ? <Icon size={17} className="mt-0.5 flex-shrink-0 text-brand" /> : <span className="w-[17px]" />}
      <dt className="w-20 flex-shrink-0 text-sm text-muted">{label}</dt>
      <dd className="min-w-0 flex-1 text-right text-sm font-medium leading-relaxed text-brand-dark">
        {value || '입력 필요'}
      </dd>
    </div>
  )
}

function SettingRow({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof MapPin
  title: string
  description: string
}) {
  return (
    <button className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-black/[0.02]">
      <Icon size={18} className="text-brand" />
      <span className="flex-1">
        <span className="block text-sm font-medium text-brand-dark">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{description}</span>
      </span>
      <ChevronRight size={17} className="text-muted" />
    </button>
  )
}
