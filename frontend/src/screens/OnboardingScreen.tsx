import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  ChoiceChip,
  Notice,
  PageIntro,
  Panel,
  ScreenHeader,
} from '../components/ui'
import { useAuth } from '../lib/auth'
import { useProfile } from '../lib/storage'
import {
  BUSINESS_AGE_OPTIONS,
  BUSINESS_STATUS_OPTIONS,
  EMPLOYEE_OPTIONS,
  INDUSTRY_OPTIONS,
  NEED_OPTIONS,
  REGION_MAP,
  REVENUE_OPTIONS,
  getProfileConsistencyWarning,
  optionByLabel,
} from '../lib/recommend'

export default function OnboardingScreen() {
  const navigate = useNavigate()
  const { profile, loading, saveProfile } = useProfile()
  const { markOnboarded, logout, onboarded } = useAuth()

  // 이미 온보딩을 마친 사용자가 들어왔다면 '수정' 모드다(마이페이지 → 수정하기).
  const isEditing = onboarded

  const [industry, setIndustry] = useState('')
  const [sido, setSido] = useState('서울특별시')
  const [sigungu, setSigungu] = useState('전체')
  const [revenue, setRevenue] = useState('')
  const [employees, setEmployees] = useState('')
  const [businessStatus, setBusinessStatus] = useState('')
  const [businessAge, setBusinessAge] = useState('')
  const [needTags, setNeedTags] = useState<string[]>([])

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 프로필은 서버에서 비동기로 온다. 도착하면 폼을 채운다(마이페이지에서 수정할 때 필요).
  useEffect(() => {
    if (loading) return
    setIndustry(profile.industry)
    if (profile.regionSido) setSido(profile.regionSido)
    if (profile.regionSigungu) setSigungu(profile.regionSigungu)
    setRevenue(profile.revenue)
    setEmployees(profile.employees)
    setBusinessStatus(profile.businessStatus)
    setBusinessAge(profile.businessAge)
    setNeedTags(profile.needTags)
  }, [loading, profile])

  const submit = async () => {
    const industryOption = optionByLabel(INDUSTRY_OPTIONS, industry)
    const revenueOption = optionByLabel(REVENUE_OPTIONS, revenue)
    const employeeOption = optionByLabel(EMPLOYEE_OPTIONS, employees)
    const statusOption = optionByLabel(BUSINESS_STATUS_OPTIONS, businessStatus)
    const ageOption = optionByLabel(BUSINESS_AGE_OPTIONS, businessAge)

    const displaySigungu = sigungu === '전체' ? '' : sigungu
    const combinedRegion = displaySigungu ? `${sido} ${displaySigungu}` : sido

    setSaving(true)
    setError(null)
    try {
      await saveProfile({
        ...profile,
        industry,
        industryTags: industryOption?.tags || [],
        region: combinedRegion,
        regionSido: sido,
        regionSigungu: displaySigungu,
        revenue,
        revenueRange: revenueOption?.range || null,
        employees,
        employeesRange: employeeOption?.range || null,
        businessStatus,
        businessStatusTags: statusOption?.tags || [],
        businessAge,
        businessAgeYears: ageOption?.range || null,
        needTags,
      })
      // 서버가 onboarded_at을 채웠다. 가드가 다시 온보딩으로 되돌리지 않도록 알린다.
      markOnboarded()
      // 수정한 경우엔 바뀐 프로필로 다시 계산된 추천을 바로 보여준다.
      // (정책 찾기 화면은 마운트될 때 프로필을 새로 읽어 추천을 다시 요청한다)
      navigate(isEditing ? '/policies' : '/', { replace: true })
    } catch {
      setError('저장에 실패했습니다. 잠시 후 다시 시도해주세요.')
      setSaving(false)
    }
  }

  const toggleNeedTag = (tag: string) => {
    setNeedTags((prev) =>
      prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag],
    )
  }

  const allNeedTags = NEED_OPTIONS.map((option) => option.tag)
  const allNeedTagsSelected = allNeedTags.every((tag) => needTags.includes(tag))
  const toggleAllNeedTags = () => {
    setNeedTags(allNeedTagsSelected ? [] : allNeedTags)
  }

  const profileConsistencyWarning = getProfileConsistencyWarning(
    industry,
    businessStatus,
    employees,
  )

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      {/* 이 화면은 두 가지로 쓰인다.
          - 최초 온보딩: 로그인 직후 첫 화면이라 '뒤로'가 갈 곳이 없다. 나가려면 로그아웃뿐.
          - 마이페이지 → 수정하기: 그냥 뒤로 가면 된다. */}
      <ScreenHeader
        title={isEditing ? '내 정보 수정' : '내 정보 입력'}
        sticky={false}
        backLabel={isEditing ? '뒤로' : '로그아웃'}
        onBack={() => {
            if (isEditing) {
              navigate(-1)
            } else {
              logout()
              navigate('/login', { replace: true })
            }
        }}
      />

      <div className="no-scrollbar flex-1 overflow-y-auto">
        <PageIntro
          title="맞춤 정책 확인에 필요한 정보"
          description="입력한 정보로 지원 대상과 조건을 비교합니다."
        />

        <div className="mt-6 space-y-6 px-5 pb-6">
          <section>
            <h3 className="text-section text-ink">사업장 정보</h3>
            <p className="mt-1 text-xs text-muted">정책의 업종과 지역 조건을 확인합니다.</p>
            <div className="surface-panel mt-3 divide-y divide-line">
              <SelectRow
                label="업종"
                value={industry}
                onChange={setIndustry}
                options={INDUSTRY_OPTIONS.map((item) => item.label)}
                placeholder="선택해주세요"
              />

              <div className="flex min-h-[68px] items-center gap-3 px-4 py-2">
                <span className="w-20 shrink-0 text-sm font-medium text-muted">활동 지역</span>
                <div className="grid min-w-0 flex-1 grid-cols-2 gap-2">
                  <InlineSelect
                    id="region-sido"
                    label="시/도"
                    value={sido}
                    onChange={(nextSido) => {
                      setSido(nextSido)
                      const nextSigunguOptions = REGION_MAP[nextSido] || []
                      setSigungu(nextSigunguOptions[0] || '전체')
                    }}
                    options={Object.keys(REGION_MAP)}
                  />
                  <InlineSelect
                    id="region-sigungu"
                    label="시/군/구"
                    value={sigungu || '전체'}
                    onChange={setSigungu}
                    options={REGION_MAP[sido] || []}
                    disabled={!(REGION_MAP[sido] && REGION_MAP[sido].length > 1)}
                  />
                </div>
              </div>

              <SelectRow
                label="사업자 상태"
                value={businessStatus}
                onChange={setBusinessStatus}
                options={BUSINESS_STATUS_OPTIONS.map((item) => item.label)}
                placeholder="선택해주세요"
              />
            </div>
          </section>

          <section>
            <h3 className="text-section text-ink">사업 규모</h3>
            <p className="mt-1 text-xs text-muted">매출과 인원 기준이 있는 정책과 비교합니다.</p>
            <div className="surface-panel mt-3 divide-y divide-line">
              <SelectRow
                label="연매출 규모"
                value={revenue}
                onChange={setRevenue}
                options={REVENUE_OPTIONS.map((item) => item.label)}
                placeholder="선택해주세요"
              />
              <SelectRow
                label="직원 수"
                value={employees}
                onChange={setEmployees}
                options={EMPLOYEE_OPTIONS.map((item) => item.label)}
                placeholder="선택해주세요"
              />
              <SelectRow
                label="업력"
                value={businessAge}
                onChange={setBusinessAge}
                options={BUSINESS_AGE_OPTIONS.map((item) => item.label)}
                placeholder="선택해주세요"
              />
            </div>
            {profileConsistencyWarning && (
              <Notice tone="warning" className="mt-3">
                {profileConsistencyWarning}
              </Notice>
            )}
          </section>

          <section>
            <h3 className="text-section text-ink">관심 지원 분야</h3>
            <p className="mt-1 text-xs text-muted">여러 분야를 선택할 수 있습니다.</p>
            <Panel className="mt-3 p-3">
              <div className="grid grid-cols-4 gap-1.5">
                <ChoiceChip
                  selected={allNeedTagsSelected}
                  onClick={toggleAllNeedTags}
                  variant="compact"
                  className="w-full"
                >
                  전체 분야
                </ChoiceChip>
                {NEED_OPTIONS.map((option) => {
                  const active = needTags.includes(option.tag)
                  return (
                    <ChoiceChip
                      key={option.tag}
                      selected={active}
                      onClick={() => toggleNeedTag(option.tag)}
                      variant="compact"
                      className="w-full"
                    >
                      {option.label}
                    </ChoiceChip>
                  )
                })}
              </div>
            </Panel>
          </section>
        </div>
      </div>

      <div className="border-t border-line bg-cream/95 px-5 py-3 backdrop-blur">
        {error && (
          <Notice tone="error" className="mb-3">
            {error}
          </Notice>
        )}
        <Button
          onClick={submit}
          disabled={saving}
          full
        >
          {saving ? '저장 중…' : isEditing ? '저장하고 추천 확인' : '맞춤 정책 확인하기'}
        </Button>
      </div>
    </div>
  )
}

function SelectRow({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
  placeholder: string
}) {
  const id = `profile-${label.replace(/\s+/g, '-')}`
  return (
    <div className="flex min-h-[60px] items-center gap-3 px-4 py-2">
      <span className="w-20 shrink-0 text-sm font-medium text-muted">{label}</span>
      <div className="min-w-0 flex-1">
        <InlineSelect
          id={id}
          label={label}
          value={value}
          onChange={onChange}
          options={options}
          placeholder={placeholder}
        />
      </div>
    </div>
  )
}

function InlineSelect({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  disabled = false,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  placeholder?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    const closeOutside = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }

    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const choose = (nextValue: string) => {
    onChange(nextValue)
    setOpen(false)
    window.requestAnimationFrame(() => buttonRef.current?.focus())
  }

  return (
    <div ref={containerRef} className="relative block w-full min-w-0">
      <button
        ref={buttonRef}
        id={id}
        type="button"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-options`}
        disabled={disabled}
        onClick={() => {
          if (!open) buttonRef.current?.scrollIntoView({ block: 'nearest' })
          setOpen((current) => !current)
        }}
        className="relative h-11 w-full truncate rounded-lg bg-cream/70 px-7 text-center text-sm font-medium text-ink outline-none transition-colors focus-visible:bg-line/30 focus-visible:ring-2 focus-visible:ring-muted/25 disabled:text-subtle"
      >
        <span className={`block truncate ${value ? 'text-ink' : 'text-subtle'}`}>
          {value || placeholder || '선택해주세요'}
        </span>
        <ChevronDown
          size={16}
          strokeWidth={1.8}
          className={`pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-subtle transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <div
          id={`${id}-options`}
          role="listbox"
          aria-label={label}
          className="absolute left-1/2 top-[calc(100%+4px)] z-30 max-h-56 w-max min-w-full max-w-[260px] -translate-x-1/2 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-lift"
        >
          {placeholder && !value && (
            <div className="px-3 py-2 text-center text-xs text-subtle">{placeholder}</div>
          )}
          {options.map((option) => {
            const selected = option === value
            return (
              <button
                key={option}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => choose(option)}
                className={`flex min-h-10 w-full items-center justify-center whitespace-nowrap rounded-lg px-4 text-center text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-muted/25 ${
                  selected
                    ? 'bg-line/60 font-semibold text-ink'
                    : 'font-medium text-muted hover:bg-cream/70 active:bg-line/40'
                }`}
              >
                {option}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
