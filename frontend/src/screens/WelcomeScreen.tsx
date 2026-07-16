import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import BrandMark from '../components/BrandMark'
import { Button } from '../components/ui'
import { apiFetch } from '../lib/api'
import type { ServerProfile } from '../types'

/**
 * 로그인(및 온보딩) 직후 첫 진입에 잠깐 보여주는 환영 화면.
 *
 * 로그인하면 곧장 달력이 뜨던 흐름이 다소 무뚝뚝해서, "소복이가 챙겨준다"는 첫인상을
 * 한 박자 준다. 로그인으로 새 토큰을 받은 순간에만 지나므로 앱을 다시 열 때마다
 * 반복되지는 않는다(토큰이 남아 있으면 바로 홈으로 간다).
 */
export default function WelcomeScreen() {
  const navigate = useNavigate()
  const [ownerName, setOwnerName] = useState('')

  useEffect(() => {
    let alive = true
    apiFetch<ServerProfile>('/api/v1/users/me/profile')
      .then((profile) => {
        if (alive) setOwnerName(profile.owner_name || '')
      })
      .catch(() => {
        // 이름은 인사말을 데우는 용도일 뿐이라, 못 불러오면 '사장님'으로 조용히 넘어간다.
      })
    return () => {
      alive = false
    }
  }, [])

  const greeting = ownerName ? `${ownerName} 사장님!` : '사장님!'

  return (
    <div className="app-frame flex flex-col items-center justify-center px-8 text-center">
      <BrandMark size={88} />

      <h1 className="mt-7 text-[26px] font-extrabold leading-snug tracking-[-0.02em] text-ink">
        환영합니다,
        <br />
        {greeting}
      </h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">
        조건에 맞는 지원 정책을
        <br />
        소복이가 챙겨드릴게요.
      </p>

      <Button full className="mt-10" onClick={() => navigate('/', { replace: true })}>
        시작하기
        <ArrowRight size={18} className="ml-1" />
      </Button>
    </div>
  )
}
