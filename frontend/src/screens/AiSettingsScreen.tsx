import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ChoiceChip, Notice, PageIntro, Panel, ScreenHeader } from '../components/ui'
import { useProfile } from '../lib/storage'
import type { AiModelMode, AiModelModes } from '../types'

const DEFAULT_MODES: AiModelModes = {
  chat: 'cloud',
  recommend: 'cloud',
  policySummary: 'cloud',
  calendarCoach: 'cloud',
  documentReview: 'local',
}

const FEATURES = [
  ['chat', '챗봇', '정책 관련 질문에 답변할 때 사용합니다.'],
  ['recommend', '정책 추천', '추천 이유와 조건 설명을 만들 때 사용합니다.'],
  ['policySummary', '정책 상세 요약', '정책 내용을 간단히 정리할 때 사용합니다.'],
  ['calendarCoach', '캘린더 AI 코치', '일정에 맞는 준비 안내를 만들 때 사용합니다.'],
  ['documentReview', '서류검토', '업로드한 서류의 누락·형식을 검토할 때 사용합니다.'],
] as const

export default function AiSettingsScreen() {
  const navigate = useNavigate()
  const { profile, loading, saveProfile } = useProfile()
  const [modes, setModes] = useState<AiModelModes>(DEFAULT_MODES)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!loading) setModes(profile.aiModelModes)
  }, [loading, profile.aiModelModes])

  const selectMode = (feature: keyof AiModelModes, mode: AiModelMode) => {
    setModes((previous) => ({ ...previous, [feature]: mode }))
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await saveProfile({ ...profile, aiModelModes: modes })
      navigate('/profile', { replace: true })
    } catch {
      setError('AI 설정을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.')
      setSaving(false)
    }
  }

  return (
    <div className="app-frame flex min-h-[100dvh] flex-col bg-cream">
      <ScreenHeader title="AI 사용 방식" onBack={() => navigate(-1)} sticky={false} />

      <div className="no-scrollbar flex-1 overflow-y-auto pb-6">
        <PageIntro
          title="기능별 AI 설정"
          description="필요한 기능만 클라우드 또는 로컬 AI로 선택할 수 있습니다."
        />

        <div className="mt-6 space-y-4 px-5">
          {FEATURES.map(([key, label, description]) => (
            <Panel key={key} className="p-4">
              <p className="text-sm font-semibold text-ink">{label}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">{description}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {(['cloud', 'local'] as AiModelMode[]).map((mode) => (
                  <ChoiceChip
                    key={mode}
                    selected={modes[key] === mode}
                    onClick={() => selectMode(key, mode)}
                    className="w-full"
                  >
                    {mode === 'cloud' ? '클라우드 AI' : '로컬 AI'}
                  </ChoiceChip>
                ))}
              </div>
              {key === 'documentReview' && modes.documentReview === 'cloud' && (
                <Notice tone="warning" className="mt-3">
                  파싱된 서류 내용이 OpenAI API로 전달됩니다.
                </Notice>
              )}
            </Panel>
          ))}

          <p className="px-1 text-xs leading-relaxed text-muted">
            클라우드 AI는 OpenAI를, 로컬 AI는 이 서버에 연결된 Ollama를 사용합니다.
          </p>
        </div>
      </div>

      <div className="border-t border-line bg-cream/95 px-5 py-3 backdrop-blur">
        {error && (
          <Notice tone="error" className="mb-3">
            {error}
          </Notice>
        )}
        <Button onClick={save} disabled={loading || saving} full>
          {saving ? '저장 중…' : 'AI 설정 저장'}
        </Button>
      </div>
    </div>
  )
}
