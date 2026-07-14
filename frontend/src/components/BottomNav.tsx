import { FileCheck2, Home, MessageCircleQuestion, Search, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/', label: '홈', icon: Home, end: true },
  { to: '/policies', label: '정책 찾기', icon: Search, end: false },
  { to: '/review', label: '서류검토', icon: FileCheck2, end: false },
  { to: '/chat', label: '정책 문의', icon: MessageCircleQuestion, end: false },
  { to: '/profile', label: '마이', icon: User, end: false },
]

export default function BottomNav() {
  return (
    <nav className="sticky bottom-0 z-10 border-t border-line bg-surface/95 backdrop-blur-sm">
      <ul className="mx-auto flex max-w-[430px] items-stretch justify-around px-1 pb-2 pt-1">
        {tabs.map(({ to, label, icon: Icon, end }) => (
          <li key={to} className="flex-1">
            <NavLink to={to} end={end} className="relative flex flex-col items-center gap-0.5 py-2">
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute -top-1 h-0.5 w-7 bg-brand-dark" />}
                  <span className={isActive ? 'text-brand-dark' : 'text-brand-dark/40'}>
                    <Icon size={20} strokeWidth={isActive ? 2.2 : 1.8} />
                  </span>
                  <span
                    className={`text-[10px] ${
                      isActive ? 'font-semibold text-brand-dark' : 'font-medium text-brand-dark/45'
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
