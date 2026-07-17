import { useState } from 'react'
import {
  Bot,
  BriefcaseBusiness,
  ChevronRight,
  HeartHandshake,
  LogOut,
  MapPin,
  Pencil,
  SlidersHorizontal,
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
  const { profile, saveProfile } = useProfile()
  const [profileEditorOpen, setProfileEditorOpen] = useState(false)
  const [ownerName, setOwnerName] = useState('')
  const [storeName, setStoreName] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileSaveError, setProfileSaveError] = useState<string | null>(null)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const openProfileEditor = () => {
    setOwnerName(profile.ownerName)
    setStoreName(profile.storeName)
    setProfileSaveError(null)
    setProfileEditorOpen(true)
  }

  const saveBasicProfile = async () => {
    setSavingProfile(true)
    setProfileSaveError(null)
    try {
      await saveProfile({
        ...profile,
        ownerName: ownerName.trim(),
        storeName: storeName.trim(),
      })
      setProfileEditorOpen(false)
    } catch {
      setProfileSaveError('프로필을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    } finally {
      setSavingProfile(false)
    }
  }

  const interestLabels = profile.needTags
    .map((tag) => NEED_OPTIONS.find((item) => item.tag === tag)?.label || tag)
  const interestSummary = [interestLabels.slice(0, 2).join(' · ')]
    .concat(interestLabels.length > 2 ? `외 ${interestLabels.length - 2}개` : [])
    .filter(Boolean)
    .join(' ')

  // 헤더 아바타와 동일한 이니셜(계정 이메일 첫 글자)
  const initial = (user?.email?.trim()?.[0] || '소').toUpperCase()

  return (
    <div className="pb-8">
      <TopBar />

      {/* 헤더는 좌측 정렬. 가운데 정렬된 큰 아바타는 SNS 프로필처럼 보이는데,
          여기는 '내 사업장 정보'를 확인하는 화면이지 자기소개가 아니다. */}
      <section className="px-5 pt-4">
        <div className="flex items-center gap-4">
          <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-brand text-2xl font-bold text-cream">
            {initial}
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
          <button
            type="button"
            onClick={openProfileEditor}
            className="ml-auto inline-flex h-11 shrink-0 items-center gap-1.5 rounded-lg px-2 text-xs font-semibold text-primary transition-colors hover:bg-primary-soft active:bg-primary-soft"
          >
            <Pencil size={15} strokeWidth={1.9} />
            프로필 변경
          </button>
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
          {interestSummary && (
            <InfoRow icon={HeartHandshake} label="관심 지원" value={interestSummary} />
          )}
        </dl>

        <p className="mt-3 border-l-2 border-status-green pl-3 text-xs leading-relaxed text-muted">
          사업장 정보가 최신일수록 조건이 맞는 정책을 더 정확하게 확인할 수 있습니다.
        </p>
      </section>

      <section className="mt-8 px-5">
        <h3 className="text-section text-ink">설정 및 관리</h3>

        <div className="surface-panel mt-2 divide-y divide-line overflow-hidden">
          <SettingRow
            icon={Bot}
            title="AI 사용 방식"
            description="기능별 클라우드·로컬 AI 설정"
            onClick={() => navigate('/profile/ai-settings')}
          />
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

      {profileEditorOpen && (
        <div
          className="fixed inset-0 z-30 flex items-end bg-ink/35 p-0 sm:items-center sm:justify-center sm:p-5"
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-editor-title"
        >
          <button
            type="button"
            aria-label="프로필 변경 닫기"
            onClick={() => setProfileEditorOpen(false)}
            className="absolute inset-0 cursor-default"
          />
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void saveBasicProfile()
            }}
            className="relative w-full max-w-[430px] rounded-t-2xl bg-surface px-5 pb-6 pt-5 shadow-lift sm:rounded-2xl"
          >
            <div className="mx-auto mb-5 h-1.5 w-10 rounded-full bg-line sm:hidden" />
            <h2 id="profile-editor-title" className="text-lg font-bold text-ink">
              사용자 프로필 변경
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted">
              마이 페이지에 표시되는 이름과 사업장 이름을 수정할 수 있어요.
            </p>

            <div className="mt-6 space-y-4">
              <div>
                <label htmlFor="profile-owner-name" className="mb-2 block text-sm font-semibold text-ink">
                  이름
                </label>
                <input
                  id="profile-owner-name"
                  value={ownerName}
                  onChange={(event) => setOwnerName(event.target.value)}
                  autoComplete="name"
                  placeholder="이름을 입력해 주세요"
                  className="h-12 w-full rounded-xl border border-line bg-cream/50 px-4 text-[15px] text-ink outline-none placeholder:text-subtle focus:border-primary"
                />
              </div>
              <div>
                <label htmlFor="profile-store-name" className="mb-2 block text-sm font-semibold text-ink">
                  사업장 이름
                </label>
                <input
                  id="profile-store-name"
                  value={storeName}
                  onChange={(event) => setStoreName(event.target.value)}
                  autoComplete="organization"
                  placeholder="사업장 이름을 입력해 주세요"
                  className="h-12 w-full rounded-xl border border-line bg-cream/50 px-4 text-[15px] text-ink outline-none placeholder:text-subtle focus:border-primary"
                />
              </div>
            </div>

            {profileSaveError && (
              <p className="mt-3 text-sm font-medium text-status-red" aria-live="polite">
                {profileSaveError}
              </p>
            )}

            <div className="mt-6 grid grid-cols-2 gap-2">
              <Button variant="secondary" onClick={() => setProfileEditorOpen(false)} disabled={savingProfile}>
                취소
              </Button>
              <Button type="submit" disabled={savingProfile}>
                {savingProfile ? '저장 중...' : '저장하기'}
              </Button>
            </div>
          </form>
        </div>
      )}
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
