import { CalendarDays, Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface TopBarProps {
  onMenu?: () => void
}

// 브랜드와 저장 일정을 조용히 연결하는 공통 헤더.
export default function TopBar({ onMenu }: TopBarProps) {
  const navigate = useNavigate()

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-cream/95 px-5 backdrop-blur-sm">
      <div className="flex items-center gap-2.5">
        {onMenu ? (
          <button
            onClick={onMenu}
            className="-ml-1 p-1 text-brand-dark/70 active:opacity-60"
            aria-label="메뉴"
          >
            <Menu size={21} />
          </button>
        ) : (
          <span className="grid h-5 w-5 grid-cols-2 gap-[3px]" aria-hidden="true">
            <span className="rounded-[2px] bg-brand" />
            <span className="rounded-[2px] bg-accent/70" />
            <span className="rounded-[2px] bg-brand-light" />
            <span className="rounded-[2px] bg-brand-dark" />
          </span>
        )}
        <button onClick={() => navigate('/')} className="text-left active:opacity-60">
          <h1 className="text-[17px] font-bold tracking-[-0.02em] text-brand-dark">소복소복</h1>
        </button>
      </div>
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-semibold text-brand-dark/65 active:bg-black/5"
        aria-label="저장 일정 보기"
      >
        <CalendarDays size={17} />
        <span>내 일정</span>
      </button>
    </header>
  )
}
