import { useCallback, useEffect, useState } from 'react'
import type { Profile, SavedPolicy } from '../types'

// localStorage 기반 저장 (로그인 없이 로컬에만 보관)
const PROFILE_KEY = 'sobok.profile'
const BOOKMARKS_KEY = 'sobok.bookmarks'
const SAVED_POLICIES_KEY = 'sobok.savedPolicies'

// 기본(데모) 프로필 — 목업 화면과 동일하게 초기 세팅
export const DEFAULT_PROFILE: Profile = {
  ownerName: '김소복',
  storeName: '소복소복 베이커리 (마포본점)',
  industry: '음식점업',
  industryTags: ['restaurant'],
  region: '서울특별시 마포구',
  regionSido: '서울특별시',
  regionSigungu: '마포구',
  revenue: '2억 ~ 5억',
  revenueRange: { min: 200_000_000, max: 500_000_000 },
  employees: '상시 1~4인',
  employeesRange: { min: 1, max: 4 },
  businessStatus: '운영 중인 소상공인',
  businessStatusTags: ['small_business', 'operating_business'],
  businessAge: '1~3년',
  businessAgeYears: { min: 1, max: 3 },
  needTags: ['funding'],
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write<T>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // 저장 실패는 무시 (프라이빗 모드 등)
  }
}

export function useProfile() {
  const [profile, setProfileState] = useState<Profile>(() => ({
    ...DEFAULT_PROFILE,
    ...read<Partial<Profile>>(PROFILE_KEY, {}),
  }))

  const setProfile = useCallback((next: Profile) => {
    setProfileState(next)
    write(PROFILE_KEY, next)
  }, [])

  return { profile, setProfile }
}

export function useBookmarks() {
  const [ids, setIds] = useState<string[]>(() => read<string[]>(BOOKMARKS_KEY, []))

  useEffect(() => {
    write(BOOKMARKS_KEY, ids)
  }, [ids])

  const toggle = useCallback((id: string) => {
    setIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }, [])

  const has = useCallback((id: string) => ids.includes(id), [ids])

  return { ids, toggle, has }
}

export function useSavedPolicies() {
  const [policies, setPolicies] = useState<SavedPolicy[]>(() =>
    read<SavedPolicy[]>(SAVED_POLICIES_KEY, []),
  )

  useEffect(() => {
    write(SAVED_POLICIES_KEY, policies)
  }, [policies])

  const has = useCallback(
    (policyId: string) => policies.some((policy) => policy.policy_id === policyId),
    [policies],
  )

  const get = useCallback(
    (policyId: string) => policies.find((policy) => policy.policy_id === policyId),
    [policies],
  )

  const save = useCallback((policy: SavedPolicy) => {
    setPolicies((prev) => {
      const exists = prev.some((item) => item.policy_id === policy.policy_id)
      if (exists) {
        return prev.map((item) =>
          item.policy_id === policy.policy_id ? { ...item, ...policy } : item,
        )
      }
      return [...prev, policy]
    })
  }, [])

  const remove = useCallback((policyId: string) => {
    setPolicies((prev) => prev.filter((policy) => policy.policy_id !== policyId))
  }, [])

  const toggle = useCallback((policy: SavedPolicy) => {
    setPolicies((prev) => {
      const exists = prev.some((item) => item.policy_id === policy.policy_id)
      if (exists) {
        return prev.filter((item) => item.policy_id !== policy.policy_id)
      }
      return [...prev, policy]
    })
  }, [])

  return { policies, has, get, save, remove, toggle }
}
