import { useState } from 'react'
import { ChevronLeft, MapPin, Users, Utensils, Wallet } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useProfile } from '../lib/storage'

const OPTIONS = {
  industry: ['음식점업', '도소매업', '서비스업', '제조업', '숙박업', '기타'],
  region: ['서울시 마포구', '서울시 강남구', '경기도 성남시', '부산시 해운대구', '기타'],
  revenue: ['5천만원 미만', '5천만원 ~ 2억', '연 2억 ~ 5억', '5억 ~ 10억', '10억 이상'],
  employees: ['없음 (1인 사업)', '상시 1~4인', '상시 4인', '상시 5~9인', '10인 이상'],
}

export default function OnboardingScreen() {
  const navigate = useNavigate()
  const { profile, setProfile } = useProfile()

  const [industry, setIndustry] = useState(profile.industry)
  const [region, setRegion] = useState(profile.region)
  const [revenue, setRevenue] = useState(profile.revenue)
  const [employees, setEmployees] = useState(profile.employees)

  const submit = () => {
    setProfile({ ...profile, industry, region, revenue, employees })
    // Step 2·3은 아직 미구현 → 저장 후 홈으로 이동
    navigate('/')
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
        {/* 진행 표시 (Step 1/3) */}
        <div className="flex items-baseline justify-between">
          <span className="font-bold text-brand">Step 1 / 3</span>
          <span className="text-sm font-medium text-brand-dark/50">기본 정보 입력</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10">
          <div className="h-full w-1/3 rounded-full bg-brand" />
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
            options={OPTIONS.industry}
            placeholder="업종을 선택해주세요"
          />
          <SelectField
            label="활동 지역"
            icon={MapPin}
            value={region}
            onChange={setRegion}
            options={OPTIONS.region}
            placeholder="지역을 선택해주세요"
          />
          <SelectField
            label="연매출 규모"
            icon={Wallet}
            value={revenue}
            onChange={setRevenue}
            options={OPTIONS.revenue}
            placeholder="연매출 범위를 선택해주세요"
          />
          <SelectField
            label="직원 수 (상시 근로자)"
            icon={Users}
            value={employees}
            onChange={setEmployees}
            options={OPTIONS.employees}
            placeholder="직원 수를 선택해주세요"
          />
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
