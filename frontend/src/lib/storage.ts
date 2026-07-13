// 프로필과 저장 정책은 이제 서버가 소유한다(로그인 필수).
// localStorage에는 JWT만 남는다 — lib/api.ts 참고.
//
// 기존 DEFAULT_PROFILE(김소복 베이커리 데모 데이터)은 제거했다. 그게 있으면 신규
// 사용자도 남의 프로필로 추천을 받게 되고, 온보딩을 건너뛴 것을 눈치채지 못한다.

import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from './api'
import { EMPTY_PROFILE, toProfile, toServerProfile } from './profile'
import type { Profile, SavedPolicy, ServerProfile } from '../types'

export { EMPTY_PROFILE } from './profile'

// 목업 혜택 카드(data/benefits.ts) 북마크. 챗봇 화면이 아직 목업이라 남겨둔다.
// 서버 즐겨찾기(useSavedPolicies)와는 다른 개념이다 — 저쪽은 실제 정책 UUID를 다룬다.
// 챗봇 담당자가 RAG로 교체하면 이것도 함께 정리한다.
const BOOKMARKS_KEY = 'sobok.bookmarks'

export function useBookmarks() {
  const [ids, setIds] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(BOOKMARKS_KEY)
      return raw ? (JSON.parse(raw) as string[]) : []
    } catch {
      return []
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(ids))
    } catch {
      // 저장 실패는 무시 (프라이빗 모드 등)
    }
  }, [ids])

  const toggle = useCallback((id: string) => {
    setIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }, [])

  const has = useCallback((id: string) => ids.includes(id), [ids])

  return { ids, toggle, has }
}

export function useProfile() {
  const [profile, setProfileState] = useState<Profile>(EMPTY_PROFILE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const server = await apiFetch<ServerProfile>('/api/v1/users/me/profile')
      setProfileState(toProfile(server))
    } catch {
      setError('프로필을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  /** 프로필을 서버에 저장한다. 최초 저장이면 서버가 온보딩 완료로 표시한다. */
  const saveProfile = useCallback(async (next: Profile) => {
    const server = await apiFetch<ServerProfile>('/api/v1/users/me/profile', {
      method: 'PUT',
      json: toServerProfile(next),
    })
    setProfileState(toProfile(server))
  }, [])

  return { profile, loading, error, saveProfile, reload }
}

export function useSavedPolicies() {
  const [policies, setPolicies] = useState<SavedPolicy[]>([])
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      setPolicies(await apiFetch<SavedPolicy[]>('/api/v1/favorites'))
    } catch {
      setPolicies([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const has = useCallback(
    (policyId: string) => policies.some((policy) => policy.policy_id === policyId),
    [policies],
  )

  const save = useCallback(async (policyId: string) => {
    const saved = await apiFetch<SavedPolicy>('/api/v1/favorites', {
      method: 'POST',
      json: { policy_id: policyId },
    })
    // 서버가 저장된 정책의 최신 내용을 돌려주므로 그것으로 목록을 갱신한다.
    setPolicies((prev) => {
      const rest = prev.filter((p) => p.policy_id !== saved.policy_id)
      return [saved, ...rest]
    })
  }, [])

  const remove = useCallback(async (policyId: string) => {
    await apiFetch<void>(`/api/v1/favorites/${policyId}`, { method: 'DELETE' })
    setPolicies((prev) => prev.filter((policy) => policy.policy_id !== policyId))
  }, [])

  const toggle = useCallback(
    async (policyId: string) => {
      if (policies.some((p) => p.policy_id === policyId)) {
        await remove(policyId)
      } else {
        await save(policyId)
      }
    },
    [policies, remove, save],
  )

  return { policies, loading, has, save, remove, toggle, reload }
}
