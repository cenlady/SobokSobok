import {
  Bell,
  BriefcaseBusiness,
  CalendarSync,
  ChevronRight,
  Lock,
  LogOut,
  MapPin,
  Pencil,
  SlidersHorizontal,
  User,
  Users,
  Utensils,
  Wallet,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { Button } from '../components/ui'
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

  const initial = profile.ownerName?.trim()?.[0] || null

  return (
    <div className="pb-8">
      <TopBar />

      {/* 프로필 헤더.
          이모지 아바타를 이니셜로 바꿨다. 이모지는 "손댈 시간이 없어 대충 채웠다"는 인상을
          주고, 무엇보다 모든 사장님이 요리사인 것도 아니다. 이니셜은 에셋이 필요 없고,
          이름이 곧 그 사람이라 개인적이다. */}
      <section className="flex flex-col items-center px-5 pt-2">
        <div className="relative">
          {/* 이름이 없으면 물음표(?) 대신 중립적인 사람 아이콘을 쓴다.
              물음표는 "데이터를 못 불러왔다"는 오류처럼 읽힌다. */}
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-soft text-2xl font-bold text-primary">
            {initial ?? <User size={30} strokeWidth={1.8} className="text-primary/60" />}
          </div>
          {/* 터치 영역 44px. 보이는 원은 28px이지만 손가락이 닿는 영역은 넓힌다. */}
          <button
            onClick={() => navigate('/onboarding')}
            aria-label="프로필 수정"
            className="tap-44 absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-ink text-white ring-4 ring-cream active:scale-95"
          >
            <Pencil size={12} />
          </button>
        </div>

        <h2 className="mt-3 text-xl font-bold text-ink">
          {profile.ownerName ? `${profile.ownerName} 사장님` : '사장님'}
        </h2>
        {profile.storeName && <p className="mt-0.5 text-sm text-muted">{profile.storeName}</p>}
        {user?.email && <p className="mt-1 text-xs text-subtle">{user.email}</p>}
      </section>

      {/* 사업장 정보 */}
      <section className="mt-6 px-5">
        <div className="flex items-start justify-between">
          <h3 className="text-section text-ink">맞춤 정책을 위한 사업장 정보</h3>
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
        {/* '성장중' 배지를 뺐다. 아무 데이터도 근거하지 않은 장식이었다. */}
        <div className="mt-3 grid grid-cols-2 gap-3">
          <InfoTile icon={Wallet} label="매출 규모" value={profile.revenue} />
          <InfoTile icon={Users} label="직원 수" value={profile.employees} />
        </div>

        {profile.needTags.length > 0 && (
          <div className="mt-3 rounded-2xl bg-white p-4 shadow-card">
            <p className="text-xs text-subtle">관심 지원</p>
            <p className="mt-1 text-sm font-semibold text-ink">
              {profile.needTags
                .map((tag) => NEED_OPTIONS.find((item) => item.tag === tag)?.label || tag)
                .join(' · ')}
            </p>
          </div>
        )}
      </section>

      {/* 설정 및 관리 */}
      <section className="mt-8 px-5">
        <h3 className="text-section text-ink">설정 및 관리</h3>
        {/* 아이콘 배경을 뉴트럴로 통일했다. 항목마다 파랑·오렌지·회색을 돌려쓰면
            색이 아무 의미도 갖지 못하고 화면만 시끄러워진다. */}
        <div className="mt-4 divide-y divide-line overflow-hidden rounded-2xl bg-white shadow-card">
          <div className="flex items-center gap-3 p-4">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-line/60">
              <Bell size={17} strokeWidth={1.8} className="text-muted" />
            </span>
            <span className="flex-1">
              <span className="block text-sm font-semibold text-ink">알림 설정</span>
              <span className="block text-xs text-subtle">지원금 소식 및 마감 알림</span>
            </span>
            <button
              onClick={() => setAlarm((v) => !v)}
              aria-label="알림 설정 전환"
              className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                alarm ? 'bg-primary' : 'bg-line'
              }`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all ${
                  alarm ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          <SettingRow icon={CalendarSync} title="캘린더 연동 관리" desc="구글 캘린더 자동 동기화" />
          <SettingRow icon={Lock} title="로그인 및 보안" desc="연결된 계정 관리" />
        </div>

        {/* 로그아웃이 탈퇴보다 훨씬 흔한 동작인데, 탈퇴만 빨간 글씨라 오히려 그쪽이
            먼저 눈에 들어왔다. 로그아웃을 버튼으로 세우고 탈퇴는 아래로 물린다.
            빨강도 뺐다 — 이 앱에서 빨강은 '마감 임박'에만 쓴다. */}
        <div className="mt-8 space-y-3">
          <Button variant="secondary" full onClick={handleLogout}>
            <LogOut size={16} /> 로그아웃
          </Button>
          <button className="w-full py-2 text-center text-xs font-medium text-subtle underline underline-offset-2">
            회원 탈퇴
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
}: {
  icon: typeof MapPin
  label: string
  value: string
}) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-card">
      <Icon size={18} strokeWidth={1.8} className="text-subtle" />
      <p className="mt-2.5 text-xs text-subtle">{label}</p>
      <p className="mt-0.5 text-[15px] font-semibold text-ink">{value || '—'}</p>
    </div>
  )
}

function SettingRow({
  icon: Icon,
  title,
  desc,
}: {
  icon: typeof MapPin
  title: string
  desc: string
}) {
  return (
    <button className="flex w-full items-center gap-3 p-4 text-left active:bg-line/30">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-line/60">
        <Icon size={17} strokeWidth={1.8} className="text-muted" />
      </span>
      <span className="flex-1">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="block text-xs text-subtle">{desc}</span>
      </span>
      <ChevronRight size={18} className="text-subtle" />
    </button>
  )
}
