// 서버 프로필(ServerProfile) ↔ 화면 프로필(Profile) 변환.
//
// 서버는 추천 엔진이 먹는 모양(태그 + min/max)으로 저장하고, 화면은 사람이 고르는
// 모양(라벨)으로 다룬다. 둘을 오가는 규칙을 여기 한 곳에만 둔다.

import type { Profile, ServerProfile } from '../types'
import {
  BUSINESS_AGE_OPTIONS,
  BUSINESS_STATUS_OPTIONS,
  EMPLOYEE_OPTIONS,
  INDUSTRY_OPTIONS,
  NEED_OPTIONS,
  optionByLabel,
  REVENUE_OPTIONS,
} from './recommend'

export const EMPTY_PROFILE: Profile = {
  ownerName: '',
  storeName: '',
  industry: '',
  industryTags: [],
  region: '',
  regionSido: '',
  regionSigungu: '',
  revenue: '',
  revenueRange: null,
  employees: '',
  employeesRange: null,
  businessStatus: '',
  businessStatusTags: [],
  businessAge: '',
  businessAgeYears: null,
  needTags: [],
}

export function toProfile(server: ServerProfile): Profile {
  const sido = server.region?.sido || ''
  const sigungu = server.region?.sigungu || ''
  return {
    ownerName: server.owner_name || '',
    storeName: server.store_name || '',
    industry: server.industry.label || '',
    industryTags: server.industry.tags || [],
    region: [sido, sigungu].filter(Boolean).join(' '),
    regionSido: sido,
    regionSigungu: sigungu,
    revenue: server.annual_sales.label || '',
    revenueRange: toRange(server.annual_sales),
    employees: server.employees.label || '',
    employeesRange: toRange(server.employees),
    businessStatus: server.business_status.label || '',
    businessStatusTags: server.business_status.tags || [],
    businessAge: server.business_age.label || '',
    businessAgeYears: toRange(server.business_age),
    needTags: server.need_tags || [],
  }
}

export function toServerProfile(profile: Profile): ServerProfile {
  return {
    owner_name: profile.ownerName || null,
    store_name: profile.storeName || null,
    region: { sido: profile.regionSido || null, sigungu: profile.regionSigungu || null },
    industry: {
      label: profile.industry || null,
      tags: profile.industryTags.length
        ? profile.industryTags
        : optionByLabel(INDUSTRY_OPTIONS, profile.industry)?.tags || [],
    },
    business_status: {
      label: profile.businessStatus || null,
      tags: profile.businessStatusTags.length
        ? profile.businessStatusTags
        : optionByLabel(BUSINESS_STATUS_OPTIONS, profile.businessStatus)?.tags || [],
    },
    annual_sales: {
      label: profile.revenue || null,
      ...(profile.revenueRange || optionByLabel(REVENUE_OPTIONS, profile.revenue)?.range || {}),
    },
    employees: {
      label: profile.employees || null,
      ...(profile.employeesRange || optionByLabel(EMPLOYEE_OPTIONS, profile.employees)?.range || {}),
    },
    business_age: {
      label: profile.businessAge || null,
      ...(profile.businessAgeYears ||
        optionByLabel(BUSINESS_AGE_OPTIONS, profile.businessAge)?.range ||
        {}),
    },
    need_tags: profile.needTags.length
      ? profile.needTags
      : NEED_OPTIONS.filter((o) => profile.needTags.includes(o.tag)).map((o) => o.tag),
  }
}

/** null과 undefined를 구분하지 않고 {min, max}만 뽑는다. 상한 없음은 max: null. */
function toRange(value: { min?: number | null; max?: number | null }) {
  if (value.min == null && value.max == null) return null
  return { min: value.min ?? null, max: value.max ?? null }
}
