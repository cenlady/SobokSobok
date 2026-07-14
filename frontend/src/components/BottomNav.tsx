import { CalendarDays, FileText, MessageCircle, Search, User } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

// 홈은 달력이다. 정책 찾기 안에 전체 조회·맞춤 추천·저장한 정책이 들어간다.
//
// 아이콘 톤을 맞췄다. Bot·FileCheck2는 면이 꽉 차 있어 다른 라인 아이콘들 사이에서
// 혼자 무거워 보였다. 전부 선으로 그려진 것들로 통일한다.
const tabs = [
  { to: '/', label: '홈', icon: CalendarDays, end: true },
  { to: '/policies', label: '정책 찾기', icon: Search, end: false },
  { to: '/review', label: '서류검토', icon: FileText, end: false },
  { to: '/chat', label: '도우미', icon: MessageCircle, end: false },
  { to: '/profile', label: '마이', icon: User, end: false },
]

export default function BottomNav() {
  const { pathname } = useLocation()

  return (
    <nav className="z-10 shrink-0 border-t border-line bg-cream/95 backdrop-blur">
      <ul className="mx-auto flex max-w-[430px] items-stretch justify-around px-1.5 py-1.5">
        {tabs.map(({ to, label, icon: Icon, end }) => (
          <li key={to} className="min-w-0 flex-1 px-0.5">
            {/* 탭 하나의 높이를 44px 이상으로. 하단바는 가장 자주 눌리는 곳이다. */}
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) => {
                const active = isActive || (to === '/policies' && pathname.startsWith('/policy/'))
                return `flex h-12 flex-col items-center justify-center gap-0.5 rounded-xl outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/20 ${
                  active ? 'bg-primary-soft/60' : 'active:bg-line/40'
                }`
              }}
            >
              {({ isActive }) => {
                const active = isActive || (to === '/policies' && pathname.startsWith('/policy/'))
                return (
                  <>
                  <Icon
                    size={20}
                    strokeWidth={active ? 2.2 : 1.8}
                    className={active ? 'text-primary' : 'text-muted'}
                  />
                  <span
                    className={`text-[10px] ${
                      active ? 'font-bold text-primary' : 'font-medium text-muted'
                    }`}
                  >
                    {label}
                  </span>
                  </>
                )
              }}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
