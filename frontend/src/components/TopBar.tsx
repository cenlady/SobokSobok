import { Bell, Menu } from 'lucide-react'

interface TopBarProps {
  onMenu?: () => void
}

// 홈/달력/AI상담 상단 공통 헤더 (로고 + 메뉴 + 알림)
export default function TopBar({ onMenu }: TopBarProps) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between bg-cream/95 px-5 py-4 backdrop-blur">
      <button
        onClick={onMenu}
        className="p-1 text-brand-dark/80 active:opacity-60"
        aria-label="메뉴"
      >
        <Menu size={26} strokeWidth={2.2} />
      </button>
      <h1 className="text-2xl font-extrabold tracking-tight text-brand">소복소복</h1>
      <button className="p-1 text-brand/90 active:opacity-60" aria-label="알림">
        <Bell size={24} strokeWidth={2} />
      </button>
    </header>
  )
}
