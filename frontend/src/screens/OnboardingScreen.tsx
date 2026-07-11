import { useState } from 'react'
import { BriefcaseBusiness, ChevronLeft, MapPin, SlidersHorizontal, Users, Utensils, Wallet } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
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
  const { profile, setProfile } = useProfile()

  const [industry, setIndustry] = useState(profile.industry)
  const [sido, setSido] = useState(profile.regionSido || '서울특별시')
  const [sigungu, setSigungu] = useState(profile.regionSigungu || '마포구')
  const [revenue, setRevenue] = useState(profile.revenue)
  const [employees, setEmployees] = useState(profile.employees)
  const [businessStatus, setBusinessStatus] = useState(profile.businessStatus)
  const [businessAge, setBusinessAge] = useState(profile.businessAge)
  const [needTags, setNeedTags] = useState(profile.needTags)

  const submit = () => {
    const industryOption = optionByLabel(INDUSTRY_OPTIONS, industry)
    const revenueOption = optionByLabel(REVENUE_OPTIONS, revenue)
    const employeeOption = optionByLabel(EMPLOYEE_OPTIONS, employees)
    const statusOption = optionByLabel(BUSINESS_STATUS_OPTIONS, businessStatus)
    const ageOption = optionByLabel(BUSINESS_AGE_OPTIONS, businessAge)

    const displaySigungu = sigungu === '전체' ? '' : sigungu
    const combinedRegion = displaySigungu ? `${sido} ${displaySigungu}` : sido

    setProfile({
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
    navigate('/')
  }

  const toggleNeedTag = (tag: string) => {
    setNeedTags((prev) =>
      prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag],
    )
  }

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      {/* 헤더 */}
      <header className="flex items-center gap-2 px-4 py-4">
        <button onClick={() => navigate(-1)} className="p-1 text-brand-dark active:opacity-60">
          <ChevronLeft size={26} />
        </button>
        <h1 className="text-lg font-semibold text-brand-dark">소복소복 내 정보 입력</h1>
      </header>
      <div className="h-px bg-black/5" />

      <div className="flex-1 overflow-y-auto px-6 pt-6">
        {/* 진행 표시 */}
        <div className="flex items-baseline justify-between">
          <span className="font-bold text-brand">맞춤 추천 정보</span>
          <span className="text-sm font-medium text-brand-dark/50">필수 + 권장 입력</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10">
          <div className="h-full w-full rounded-full bg-brand" />
        </div>

        <h2 className="mt-8 text-2xl font-bold leading-snug text-brand-dark">
          사장님에 대해
          <br />
          조금 더 알려주세요!
        </h2>
        <p className="mt-3 text-[15px] leading-relaxed text-brand-dark/60">
          맞춤형 혜택과 지원금을 찾아드리기 위해 꼭 필요한 정보예요.
        </p>

        <div className="mt-8 space-y-6">
          <SelectField
            label="업종"
            icon={Utensils}
            value={industry}
            onChange={setIndustry}
            options={INDUSTRY_OPTIONS.map((item) => item.label)}
            placeholder="업종을 선택해주세요"
          />
          {/* 활동 지역 (시/도) */}
          <div>
            <label className="mb-2 block text-[15px] font-semibold text-brand-dark">활동 지역 (시/도)</label>
            <div className="relative">
              <select
                value={sido}
                onChange={(e) => {
                  const nextSido = e.target.value
                  setSido(nextSido)
                  const nextSigunguOptions = REGION_MAP[nextSido] || []
                  setSigungu(nextSigunguOptions[0] || '전체')
                }}
                className="w-full appearance-none rounded-2xl border border-brand-light/40 bg-white py-4 pl-4 pr-12 text-[15px] outline-none focus:border-brand text-brand-dark"
              >
                {Object.keys(REGION_MAP).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-brand-dark/40">
                <MapPin size={20} />
              </span>
            </div>
          </div>

          {/* 활동 지역 (시/군/구) */}
          <div>
            <label className="mb-2 block text-[15px] font-semibold text-brand-dark">활동 지역 (시/군/구)</label>
            <div className="relative">
              <select
                value={sigungu || '전체'}
                onChange={(e) => setSigungu(e.target.value)}
                className="w-full appearance-none rounded-2xl border border-brand-light/40 bg-white py-4 pl-4 pr-12 text-[15px] outline-none focus:border-brand text-brand-dark"
                disabled={!(REGION_MAP[sido] && REGION_MAP[sido].length > 1)}
              >
                {(REGION_MAP[sido] || []).map((sg) => (
                  <option key={sg} value={sg}>
                    {sg}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-brand-dark/40">
                <MapPin size={20} />
              </span>
            </div>
          </div>
          <SelectField
            label="사업자 상태"
            icon={BriefcaseBusiness}
            value={businessStatus}
            onChange={setBusinessStatus}
            options={BUSINESS_STATUS_OPTIONS.map((item) => item.label)}
            placeholder="현재 상태를 선택해주세요"
          />
          <SelectField
            label="연매출 규모"
            icon={Wallet}
            value={revenue}
            onChange={setRevenue}
            options={REVENUE_OPTIONS.map((item) => item.label)}
            placeholder="연매출 범위를 선택해주세요"
          />
          <SelectField
            label="직원 수 (상시 근로자)"
            icon={Users}
            value={employees}
            onChange={setEmployees}
            options={EMPLOYEE_OPTIONS.map((item) => item.label)}
            placeholder="직원 수를 선택해주세요"
          />
          <SelectField
            label="업력"
            icon={SlidersHorizontal}
            value={businessAge}
            onChange={setBusinessAge}
            options={BUSINESS_AGE_OPTIONS.map((item) => item.label)}
            placeholder="사업 운영 기간을 선택해주세요"
          />

          <div>
            <label className="mb-2 block text-[15px] font-semibold text-brand-dark">
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
                    className={`rounded-2xl border px-3 py-3 text-sm font-semibold transition-colors ${
                      active
                        ? 'border-brand bg-brand text-white'
                        : 'border-brand-light/40 bg-white text-brand-dark/70'
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

      <div className="px-6 py-5">
        <button
          onClick={submit}
          className="w-full rounded-2xl bg-brand-dark py-4 text-lg font-bold text-white active:scale-[0.99]"
        >
          맞춤 혜택 찾기
        </button>
      </div>
    </div>
  )
}

function SelectField({
  label,
  icon: Icon,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string
  icon: typeof MapPin
  value: string
  onChange: (v: string) => void
  options: string[]
  placeholder: string
}) {
  return (
    <div>
      <label className="mb-2 block text-[15px] font-semibold text-brand-dark">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full appearance-none rounded-2xl border border-brand-light/40 bg-white py-4 pl-4 pr-12 text-[15px] outline-none focus:border-brand ${
            value ? 'text-brand-dark' : 'text-brand-dark/40'
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
        <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-brand-dark/40">
          <Icon size={20} />
        </span>
      </div>
    </div>
  )
}
