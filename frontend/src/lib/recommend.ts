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
  '서울특별시': ['전체', '마포구', '강남구', '강동구', '강서구', '광진구', '동대문구', '동작구', '서대문구', '성동구', '성북구', '영등포구', '종로구'],
  '경기도': ['전체', '성남시', '수원시', '김포시', '동두천시', '시흥시', '안양시', '양주시', '연천군', '의왕시', '포천시', '화성시'],
  '인천광역시': ['전체', '계양구', '남동구', '미추홀구', '부평구', '연수구', '옹진군'],
  '부산광역시': ['전체', '해운대구', '수영구', '영도구'],
  '대구광역시': ['전체', '중구', '수성구', '달서구'],
  '광주광역시': ['전체', '동구', '서구', '남구', '북구', '광산구'],
  '대전광역시': ['전체', '동구', '중구', '서구', '유성구', '대덕구'],
  '울산광역시': ['전체', '중구', '남구', '동구', '북구', '울주군'],
  '세종특별자치시': ['전체'],
  '강원특별자치도': ['전체', '영월군', '인제군', '태백시', '평창군'],
  '충청북도': ['전체', '영동군', '옥천군', '충주시', '청주시'],
  '충청남도': ['전체', '당진시', '보령시', '아산시', '예산군', '천안시'],
  '전북특별자치도': ['전체', '고창군', '군산시', '순창군', '익산시', '임실군', '전주시'],
  '전라남도': ['전체', '목포시', '여수시', '순천시', '나주시'],
  '경상북도': ['전체', '경주시', '구미시', '상주시', '영천시', '청송군', '포항시'],
  '경상남도': ['전체', '거제시', '거창군', '합천군', '창원시', '진주시'],
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
