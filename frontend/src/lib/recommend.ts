import type { Profile } from '../types'

export const INDUSTRY_OPTIONS = [
  { label: '음식점업', tags: ['restaurant'] },
  { label: '도소매업', tags: ['retail'] },
  { label: '서비스업', tags: ['other_business'] },
  { label: '제조업', tags: ['manufacturing'] },
  { label: '숙박/관광업', tags: ['tourism'] },
  { label: '전통시장/상점가', tags: ['market', 'retail'] },
  { label: '디지털/IT', tags: ['digital', 'information_communication'] },
]

export const REGION_MAP: Record<string, string[]> = {
  '서울특별시': ['전체', '종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'],
  '부산광역시': ['전체', '중구', '서구', '동구', '영도구', '부산진구', '동래구', '남구', '북구', '해운대구', '사하구', '금정구', '강서구', '연제구', '수영구', '사상구', '기장군'],
  '대구광역시': ['전체', '중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'],
  '인천광역시': ['전체', '중구', '동구', '미추홀구', '연수구', '남동구', '부평구', '계양구', '서구', '강화군', '옹진군'],
  '광주광역시': ['전체', '동구', '서구', '남구', '북구', '광산구'],
  '대전광역시': ['전체', '동구', '중구', '서구', '유성구', '대덕구'],
  '울산광역시': ['전체', '중구', '남구', '동구', '북구', '울주군'],
  '세종특별자치시': ['전체'],
  '경기도': ['전체', '수원시', '성남시', '의정부시', '안양시', '부천시', '광명시', '평택시', '동두천시', '안산시', '고양시', '과천시', '구리시', '남양주시', '오산시', '시흥시', '군포시', '의왕시', '하남시', '용인시', '파주시', '이천시', '안성시', '김포시', '화성시', '광주시', '양주시', '포천시', '여주시', '연천군', '가평군', '양평군'],
  '강원특별자치도': ['전체', '춘천시', '원주시', '강릉시', '동해시', '태백시', '속초시', '삼척시', '홍천군', '횡성군', '영월군', '평창군', '정선군', '철원군', '화천군', '양구군', '인제군', '고성군', '양양군'],
  '충청북도': ['전체', '청주시', '충주시', '제천시', '보은군', '옥천군', '영동군', '증평군', '진천군', '괴산군', '음성군', '단양군'],
  '충청남도': ['전체', '천안시', '공주시', '보령시', '아산시', '서산시', '논산시', '계룡시', '당진시', '금산군', '부여군', '서천군', '청양군', '홍성군', '예산군', '태안군'],
  '전북특별자치도': ['전체', '전주시', '군산시', '익산시', '정읍시', '남원시', '김제시', '완주군', '진안군', '무주군', '장수군', '임실군', '순창군', '고창군', '부안군'],
  '전라남도': ['전체', '목포시', '여수시', '순천시', '나주시', '광양시', '담양군', '곡성군', '구례군', '고흥군', '보성군', '화순군', '장흥군', '강진군', '해남군', '영암군', '무안군', '함평군', '영광군', '장성군', '완도군', '진도군', '신안군'],
  '경상북도': ['전체', '포항시', '경주시', '김천시', '안동시', '구미시', '영주시', '영천시', '상주시', '문경시', '경산시', '군위군', '의성군', '청송군', '영양군', '영덕군', '청도군', '고령군', '성주군', '칠곡군', '예천군', '봉화군', '울진군', '울릉군'],
  '경상남도': ['전체', '창원시', '진주시', '통영시', '사천시', '김해시', '밀양시', '거제시', '양산시', '의령군', '함안군', '창녕군', '고성군', '남해군', '하동군', '산청군', '함양군', '거창군', '합천군'],
  '제주특별자치도': ['전체', '제주시', '서귀포시']
}

export const REVENUE_OPTIONS = [
  { label: '5천만원 미만', range: { min: 0, max: 49_999_999 } },
  { label: '5천만원 ~ 2억', range: { min: 50_000_000, max: 200_000_000 } },
  { label: '2억 ~ 5억', range: { min: 200_000_000, max: 500_000_000 } },
  { label: '5억 ~ 10억', range: { min: 500_000_000, max: 1_000_000_000 } },
  { label: '10억 이상', range: { min: 1_000_000_000, max: null } },
]

export const EMPLOYEE_OPTIONS = [
  { label: '1인 사업', range: { min: 1, max: 1 } },
  { label: '상시 1~4인', range: { min: 1, max: 4 } },
  { label: '상시 5~9인', range: { min: 5, max: 9 } },
  { label: '10인 이상', range: { min: 10, max: null } },
]

export const BUSINESS_STATUS_OPTIONS = [
  { label: '운영 중인 소상공인', tags: ['small_business', 'operating_business'] },
  { label: '예비창업자', tags: ['pre_founder'] },
  { label: '폐업/재기 준비', tags: ['closing_business'] },
  { label: '소공인', tags: ['small_manufacturer', 'small_business'] },
  { label: '전통시장/상점가 상인', tags: ['traditional_market', 'small_business'] },
]

export const BUSINESS_AGE_OPTIONS = [
  { label: '1년 미만', range: { min: 0, max: 0 } },
  { label: '1~3년', range: { min: 1, max: 3 } },
  { label: '3~7년', range: { min: 3, max: 7 } },
  { label: '7년 이상', range: { min: 7, max: null } },
]

export const NEED_OPTIONS = [
  { label: '자금', tag: 'funding' },
  { label: '교육/컨설팅', tag: 'education_consulting' },
  { label: '디지털/온라인', tag: 'digital' },
  { label: '판로/마케팅', tag: 'marketing' },
  { label: '시설/장비', tag: 'facility' },
  { label: '재기/폐업지원', tag: 'recovery' },
  { label: '고용/인력', tag: 'employment' },
]

export function optionByLabel<T extends { label: string }>(options: T[], label: string) {
  return options.find((option) => option.label === label)
}

export function getProfileConsistencyWarning(
  industryLabel: string,
  businessStatusLabel: string,
  employeeLabel: string,
) {
  const industry = optionByLabel(INDUSTRY_OPTIONS, industryLabel)
  const status = optionByLabel(BUSINESS_STATUS_OPTIONS, businessStatusLabel)
  const employees = optionByLabel(EMPLOYEE_OPTIONS, employeeLabel)
  if (!industry || !status || !employees || !status.tags.includes('small_business')) return null

  const employeeMinimum = employees.range.min
  if (employeeMinimum === null) return null
  const threshold = industry.tags.length === 1 && industry.tags[0] === 'manufacturing' ? 10 : 5
  if (employeeMinimum < threshold) return null

  return `${industry.label}의 직원 수(${employeeMinimum}명 이상)와 소상공인 선택이 충돌할 수 있어요. 소상공인 확인서 기준을 먼저 확인해 주세요.`
}

export function buildRecommendationRequest(profile: Profile) {
  return {
    region: {
      sido: profile.regionSido || null,
      sigungu: profile.regionSigungu || null,
    },
    industry_tags:
      profile.industryTags.length > 0
        ? profile.industryTags
        : optionByLabel(INDUSTRY_OPTIONS, profile.industry)?.tags || [],
    business_status_tags:
      profile.businessStatusTags.length > 0
        ? profile.businessStatusTags
        : optionByLabel(BUSINESS_STATUS_OPTIONS, profile.businessStatus)?.tags || [],
    employees:
      profile.employeesRange ||
      optionByLabel(EMPLOYEE_OPTIONS, profile.employees)?.range ||
      null,
    annual_sales_krw:
      profile.revenueRange ||
      optionByLabel(REVENUE_OPTIONS, profile.revenue)?.range ||
      null,
    business_age_years:
      profile.businessAgeYears ||
      optionByLabel(BUSINESS_AGE_OPTIONS, profile.businessAge)?.range ||
      null,
    need_tags: profile.needTags,
    use_vectors: true,
  }
}
