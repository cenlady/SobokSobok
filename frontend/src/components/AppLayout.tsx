import { Outlet } from 'react-router-dom'
import BottomNav from './BottomNav'

// 탭 화면 공통 셸: 모바일 프레임 + 스크롤 영역 + 하단 탭
export default function AppLayout() {
  return (
    <div className="app-frame flex h-[100dvh] max-h-[100dvh] flex-col overflow-hidden">
      <main className="no-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  )
}
