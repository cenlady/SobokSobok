import { Bot, FileCheck2, Home, Search, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'

// 홈은 이제 달력이다. 정책 찾기 안에 전체 조회·AI 추천·저장한 정책이 들어간다.
const tabs = [
  { to: '/', label: '홈', icon: Home, end: true },
  { to: '/policies', label: '정책 찾기', icon: Search, end: false },
  { to: '/review', label: '서류검토', icon: FileCheck2, end: false },
  { to: '/chat', label: '챗봇', icon: Bot, end: false },
  { to: '/profile', label: '마이', icon: User, end: false },
]

export default function BottomNav() {
  return (
    <nav className="sticky bottom-0 z-10 border-t border-black/5 bg-cream/95 backdrop-blur">
      <ul className="mx-auto flex max-w-[430px] items-stretch justify-around px-1 py-2">
        {tabs.map(({ to, label, icon: Icon, end }) => (
          <li key={to} className="flex-1">
            <NavLink to={to} end={end} className="flex flex-col items-center gap-1 py-1">
              {({ isActive }) => (
                <>
                  <span
                    className={`flex h-8 w-14 items-center justify-center rounded-full transition-colors ${
                      isActive ? 'bg-accent-soft text-accent' : 'text-brand-dark/50'
                    }`}
                  >
                    <Icon size={21} strokeWidth={isActive ? 2.4 : 2} />
                  </span>
                  <span
                    className={`text-[10.5px] font-medium ${
                      isActive ? 'text-accent' : 'text-brand-dark/50'
                    }`}
                  >
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
