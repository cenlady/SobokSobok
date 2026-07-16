import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import BrandMark from './BrandMark'
import { useAuth } from '../lib/auth'

/**
 * 상단 공통 헤더 — 유튜브 뮤직 스타일.
 *
 * 왼쪽은 브랜드 락업(로고 + 소복소복), 오른쪽은 액션 아이콘과 원형 프로필 아바타.
 * 하단 얇은 구분선으로 헤더를 하나의 '바'로 앉힌다. 이게 없으면 배경색이 본문과 같아
 * 로고가 콘텐츠 위에 붕 떠 따로 노는 느낌이 든다.
 *
 * 위계: [페이지 타이틀 26px] > [로고 19px]. 매 화면에 있는 요소라 조용해야 한다.
 */
export default function TopBar() {
  const { user } = useAuth()
  const initial = (user?.email?.trim()?.[0] || '소').toUpperCase()

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line/70 bg-cream/90 px-4 py-2.5 backdrop-blur">
      <Link to="/" aria-label="홈" className="flex items-center gap-2 rounded-full pl-1 pr-2">
        <BrandMark size={27} framed={false} />
        <span className="text-[19px] font-extrabold tracking-tight text-brand">소복소복</span>
      </Link>

      <div className="flex items-center gap-0.5">
        <Link
          to="/policies"
          aria-label="정책 검색"
          className="grid h-10 w-10 place-items-center rounded-full text-ink transition-colors active:bg-line/40"
        >
          <Search size={22} strokeWidth={2} />
        </Link>
        <Link
          to="/profile"
          aria-label="내 정보"
          className="grid h-9 w-9 place-items-center rounded-full bg-brand text-[15px] font-bold text-cream transition-transform active:scale-95"
        >
          {initial}
        </Link>
      </div>
    </header>
  )
}
