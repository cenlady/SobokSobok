import { Outlet } from 'react-router-dom'
import BottomNav from './BottomNav'

// 탭 화면 공통 셸: 모바일 프레임 + 스크롤 영역 + 하단 탭
export default function AppLayout() {
  return (
    <div className="app-frame flex flex-col">
      <main className="no-scrollbar flex-1 overflow-y-auto">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  )
}
