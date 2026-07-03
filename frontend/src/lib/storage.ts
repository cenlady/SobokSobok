import { useCallback, useEffect, useState } from 'react'
import type { Profile } from '../types'

// localStorage 기반 저장 (로그인 없이 로컬에만 보관)
const PROFILE_KEY = 'sobok.profile'
const BOOKMARKS_KEY = 'sobok.bookmarks'

// 기본(데모) 프로필 — 목업 화면과 동일하게 초기 세팅
export const DEFAULT_PROFILE: Profile = {
  ownerName: '김소복',
  storeName: '소복소복 베이커리 (마포본점)',
  industry: '음식점업',
  region: '서울시 마포구',
  revenue: '연 2억 ~ 5억',
  employees: '상시 4인',
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
  const [profile, setProfileState] = useState<Profile>(() =>
    read<Profile>(PROFILE_KEY, DEFAULT_PROFILE),
  )

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
