import { useEffect, useState } from 'react'
import { ChevronDown, ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
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
  const [sigungu, setSigungu] = useState('마포구')
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

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      {/* 이 화면은 두 가지로 쓰인다.
          - 최초 온보딩: 로그인 직후 첫 화면이라 '뒤로'가 갈 곳이 없다. 나가려면 로그아웃뿐.
          - 마이페이지 → 수정하기: 그냥 뒤로 가면 된다. */}
      <header className="flex h-14 items-center gap-2 border-b border-line px-4">
        <button
          onClick={() => {
            if (isEditing) {
              navigate(-1)
            } else {
              logout()
              navigate('/login', { replace: true })
            }
          }}
          className="p-1 text-brand-dark active:opacity-60"
          aria-label={isEditing ? '뒤로' : '로그아웃'}
        >
          <ChevronLeft size={23} />
        </button>
        <h1 className="text-base font-semibold text-brand-dark">
          {isEditing ? '사업장 정보 수정' : '사업장 정보 등록'}
        </h1>
      </header>

      <div className="flex-1 overflow-y-auto px-5 pt-6">
        {/* 진행 표시 */}
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-semibold tracking-[0.08em] text-brand">정책 검색 기준</span>
          <span className="text-xs text-muted">필수 · 권장 정보</span>
        </div>
        <div className="mt-3 h-1 overflow-hidden bg-line">
          <div className="h-full w-full bg-brand" />
        </div>

        <h2 className="mt-8 page-title">사업장 기본 정보를 입력해주세요</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          입력한 정보는 정책의 지역·업종·규모 조건을 확인하는 데 사용됩니다.
        </p>

        <div className="mt-8 space-y-5">
          <SelectField
            label="업종"
            value={industry}
            onChange={setIndustry}
            options={INDUSTRY_OPTIONS.map((item) => item.label)}
            placeholder="업종을 선택해주세요"
          />
          {/* 활동 지역 (시/도) */}
          <div>
            <label className="mb-2 block text-sm font-semibold text-brand-dark">활동 지역 (시/도)</label>
            <div className="relative">
              <select
                value={sido}
                onChange={(e) => {
                  const nextSido = e.target.value
                  setSido(nextSido)
                  const nextSigunguOptions = REGION_MAP[nextSido] || []
                  setSigungu(nextSigunguOptions[0] || '전체')
                }}
                className="field-control appearance-none pr-10"
              >
                {Object.keys(REGION_MAP).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted">
                <ChevronDown size={18} />
              </span>
            </div>
          </div>

          {/* 활동 지역 (시/군/구) */}
          <div>
            <label className="mb-2 block text-sm font-semibold text-brand-dark">활동 지역 (시/군/구)</label>
            <div className="relative">
              <select
                value={sigungu || '전체'}
                onChange={(e) => setSigungu(e.target.value)}
                className="field-control appearance-none pr-10 disabled:bg-black/[0.025] disabled:text-muted"
                disabled={!(REGION_MAP[sido] && REGION_MAP[sido].length > 1)}
              >
                {(REGION_MAP[sido] || []).map((sg) => (
                  <option key={sg} value={sg}>
                    {sg}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted">
                <ChevronDown size={18} />
              </span>
            </div>
          </div>
          <SelectField
            label="사업자 상태"
            value={businessStatus}
            onChange={setBusinessStatus}
            options={BUSINESS_STATUS_OPTIONS.map((item) => item.label)}
            placeholder="현재 상태를 선택해주세요"
          />
          <SelectField
            label="연매출 규모"
            value={revenue}
            onChange={setRevenue}
            options={REVENUE_OPTIONS.map((item) => item.label)}
            placeholder="연매출 범위를 선택해주세요"
          />
          <SelectField
            label="직원 수 (상시 근로자)"
            value={employees}
            onChange={setEmployees}
            options={EMPLOYEE_OPTIONS.map((item) => item.label)}
            placeholder="직원 수를 선택해주세요"
          />
          <SelectField
            label="업력"
            value={businessAge}
            onChange={setBusinessAge}
            options={BUSINESS_AGE_OPTIONS.map((item) => item.label)}
            placeholder="사업 운영 기간을 선택해주세요"
          />

          <div>
            <label className="mb-2 block text-sm font-semibold text-brand-dark">
              원하는 지원 유형
            </label>
            <div className="grid grid-cols-2 gap-2">
              {NEED_OPTIONS.map((option) => {
                const active = needTags.includes(option.tag)
                return (
                  <button
                    key={option.tag}
                    type="button"
                    onClick={() => toggleNeedTag(option.tag)}
                    className={`rounded-lg border px-3 py-3 text-sm font-medium transition-colors ${
                      active
                        ? 'border-brand-dark bg-brand-dark text-white'
                        : 'border-line bg-surface text-brand-dark/70'
                    }`}
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-line bg-surface px-5 py-4">
        {error && (
          <p className="mb-3 text-center text-sm font-medium text-status-red">{error}</p>
        )}
        <button
          onClick={submit}
          disabled={saving}
          className="primary-button w-full py-3.5 text-base"
        >
          {saving ? '저장 중…' : isEditing ? '저장하고 추천 다시 받기' : '맞춤 혜택 찾기'}
        </button>
      </div>
    </div>
  )
}

function SelectField({
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
  return (
    <div>
      <label className="mb-2 block text-sm font-semibold text-brand-dark">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`field-control appearance-none pr-10 ${
            value ? 'text-brand-dark' : 'text-muted'
          }`}
        >
          <option value="" disabled>
            {placeholder}
          </option>
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted">
          <ChevronDown size={18} />
        </span>
      </div>
    </div>
  )
}
