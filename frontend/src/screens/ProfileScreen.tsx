import { useState } from 'react'
import {
  Bell,
  Bot,
  BriefcaseBusiness,
  CalendarSync,
  ChevronRight,
  Lock,
  LogOut,
  MapPin,
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

  const initial = profile.ownerName?.trim()?.[0] || null
  const interestLabel = profile.needTags
    .map((tag) => NEED_OPTIONS.find((item) => item.tag === tag)?.label || tag)
    .join(', ')

  return (
    <div className="pb-8">
      <TopBar />

      {/* 헤더는 좌측 정렬. 가운데 정렬된 큰 아바타는 SNS 프로필처럼 보이는데,
          여기는 '내 사업장 정보'를 확인하는 화면이지 자기소개가 아니다. */}
      <section className="px-5 pt-4">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-line bg-surface text-xl font-bold text-brand">
            {/* 이름이 없으면 물음표(?) 대신 사람 아이콘.
                물음표는 "데이터를 못 불러왔다"는 오류처럼 읽힌다. */}
            {initial ?? <User size={26} strokeWidth={1.8} className="text-subtle" />}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-[0.08em] text-brand">내 사업장</p>
            <h2 className="mt-1 text-xl font-bold tracking-[-0.02em] text-ink">
              {profile.ownerName ? `${profile.ownerName} 사장님` : '사장님'}
            </h2>
            <p className="mt-1 truncate text-sm text-muted">
              {profile.storeName || '사업장 이름 미입력'}
            </p>
          </div>
        </div>
        {user?.email && (
          <p className="mt-4 border-t border-line pt-3 text-xs text-subtle">{user.email}</p>
        )}
      </section>

      {/* 사업장 정보 — 2열 타일 대신 라벨/값 행 목록.
          타일은 값이 짧을 때만 예쁘고, '서울특별시 마포구'처럼 길어지면 줄바꿈으로
          높이가 들쭉날쭉해진다. 행 목록은 훑기도 쉽고 값 길이에도 강하다. */}
      <section className="mt-8 px-5">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h3 className="text-section text-ink">사업장 정보</h3>
            <p className="mt-1 text-xs text-muted">정책 조건 확인에 사용하는 정보입니다.</p>
          </div>
          <button
            onClick={() => navigate('/onboarding')}
            className="flex h-11 shrink-0 items-center whitespace-nowrap text-xs font-semibold text-primary"
          >
            수정하기 <ChevronRight size={15} />
          </button>
        </div>

        <dl className="surface-panel mt-2 divide-y divide-line overflow-hidden">
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
        <h3 className="text-section text-ink">설정 및 관리</h3>

        <div className="surface-panel mt-2 divide-y divide-line overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3.5">
            <Bell size={18} strokeWidth={1.8} className="shrink-0 text-brand" />
            <span className="flex-1">
              <span className="block text-sm font-medium text-ink">마감 알림</span>
              <span className="mt-0.5 block text-xs text-muted">저장한 정책의 신청 마감 안내</span>
            </span>
            <button
              onClick={() => setAlarm((value) => !value)}
              role="switch"
              aria-checked={alarm}
              aria-label="마감 알림"
              className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                alarm ? 'bg-primary' : 'bg-line'
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-surface shadow-sm transition-all ${
                  alarm ? 'left-6' : 'left-1'
                }`}
              />
            </button>
          </div>

          <SettingRow
            icon={Bot}
            title="AI 사용 방식"
            description="기능별 클라우드·로컬 AI 설정"
            onClick={() => navigate('/profile/ai-settings')}
          />
          <SettingRow
            icon={CalendarSync}
            title="Google Calendar"
            description="정책 마감일 일정 등록"
          />
          <SettingRow icon={Lock} title="로그인 및 보안" description="계정과 로그인 정보 관리" />
        </div>

        {/* 로그아웃이 탈퇴보다 훨씬 흔한 동작인데, 탈퇴만 빨간 글씨면 그쪽이 먼저
            눈에 들어온다. 로그아웃을 버튼으로 세우고 탈퇴는 아래로 물린다.
            빨강도 뺐다 — 이 앱에서 빨강은 '마감 임박'에만 쓴다. */}
        <div className="mt-8 space-y-3 border-t border-line pt-6">
          <Button variant="secondary" full onClick={handleLogout}>
            <LogOut size={16} /> 로그아웃
          </Button>
          <button className="h-11 w-full text-center text-xs font-medium text-subtle underline underline-offset-2">
            회원 탈퇴
          </button>
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
      {Icon ? (
        <Icon size={17} strokeWidth={1.8} className="mt-0.5 shrink-0 text-brand" />
      ) : (
        <span className="w-[17px] shrink-0" />
      )}
      <dt className="w-20 shrink-0 text-sm text-muted">{label}</dt>
      {/* 값이 없으면 '—'가 아니라 '입력 필요'. 사용자가 할 일이 있다는 걸 알려준다. */}
      <dd
        className={`min-w-0 flex-1 text-right text-sm leading-relaxed ${
          value ? 'font-medium text-ink' : 'text-subtle'
        }`}
      >
        {value || '입력 필요'}
      </dd>
    </div>
  )
}

function SettingRow({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: typeof MapPin
  title: string
  description: string
  onClick?: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-cream/60 active:bg-cream"
    >
      <Icon size={18} strokeWidth={1.8} className="shrink-0 text-brand" />
      <span className="flex-1">
        <span className="block text-sm font-medium text-ink">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{description}</span>
      </span>
      <ChevronRight size={17} className="shrink-0 text-subtle" />
    </button>
  )
}
