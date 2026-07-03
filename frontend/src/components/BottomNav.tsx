import { Calendar, Bot, Home, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/', label: '홈', icon: Home, end: true },
  { to: '/calendar', label: '달력', icon: Calendar, end: false },
  { to: '/chat', label: 'AI 상담', icon: Bot, end: false },
  { to: '/profile', label: '내 정보', icon: User, end: false },
]

// 하단 4탭 네비게이션
export default function BottomNav() {
  return (
    <nav className="sticky bottom-0 z-10 border-t border-black/5 bg-cream/95 backdrop-blur">
      <ul className="mx-auto flex max-w-[430px] items-stretch justify-around px-2 py-2">
        {tabs.map(({ to, label, icon: Icon, end }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              end={end}
              className="flex flex-col items-center gap-1 py-1"
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`flex h-8 w-16 items-center justify-center rounded-full transition-colors ${
                      isActive ? 'bg-accent-soft text-accent' : 'text-brand-dark/50'
                    }`}
                  >
                    <Icon size={22} strokeWidth={isActive ? 2.4 : 2} />
                  </span>
                  <span
                    className={`text-[11px] font-medium ${
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
