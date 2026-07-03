import { ArrowRight, ChevronRight, CalendarDays, Sparkles, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { benefits } from '../data/benefits'
import { ddayLabel } from '../lib/format'
import { useProfile } from '../lib/storage'

export default function HomeScreen() {
  const navigate = useNavigate()
  const { profile } = useProfile()

  // 곧 마감되는 순으로 상위 노출
  const upcoming = [...benefits]
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate))
    .slice(0, 4)
  const count = upcoming.length

  return (
    <div className="pb-6">
      <TopBar />

      {/* 인사 배너 */}
      <section className="px-5">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-accent-soft to-[#FBD9A8] p-6 shadow-card">
          <Sun
            className="absolute -right-6 -top-6 text-white/40"
            size={120}
            strokeWidth={1.2}
          />
          <span className="inline-flex items-center gap-1 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-brand-dark">
            ☀️ 좋은 아침입니다!
          </span>
          <h2 className="mt-3 text-2xl font-bold leading-snug text-brand-dark">
            {profile.ownerName} 사장님,
            <br />
            오늘 챙겨야 할 혜택이 <span className="text-brand">{count}건</span> 있어요!
          </h2>
          <p className="mt-2 text-sm text-brand-dark/70">
            놓치지 않도록 소복소복 메이가 도와드릴게요.
          </p>
          <button
            onClick={() => navigate('/chat')}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-dark/20 active:scale-[0.99]"
          >
            <Sparkles size={18} /> AI 추천 시작하기
          </button>
        </div>
      </section>

      {/* 나의 혜택 달력 */}
      <section className="mt-7 px-5">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-lg font-bold text-brand-dark">
            <CalendarDays size={20} className="text-brand" /> 나의 혜택 달력
          </h3>
          <button
            onClick={() => navigate('/calendar')}
            className="flex items-center text-sm font-medium text-brand-dark/50"
          >
            전체보기 <ChevronRight size={16} />
          </button>
        </div>
        <p className="mt-1 text-sm text-brand-dark/50">곧 마감되는 정보를 확인하세요.</p>

        <div className="no-scrollbar mt-4 flex gap-3 overflow-x-auto pb-1">
          {upcoming.map((b) => (
            <button
              key={b.id}
              onClick={() => navigate(`/benefit/${b.id}`)}
              className="w-44 flex-shrink-0 rounded-2xl bg-white p-4 text-left shadow-card active:scale-[0.98]"
            >
              <div className="flex items-center justify-between">
                <span
                  className={`rounded-lg px-2 py-0.5 text-xs font-bold ${
                    b.status === 'closing'
                      ? 'bg-red-50 text-status-red'
                      : b.status === 'open'
                        ? 'bg-green-50 text-status-green'
                        : 'bg-blue-50 text-status-blue'
                  }`}
                >
                  {ddayLabel(b.dueDate)}
                </span>
                <ArrowRight size={14} className="text-brand-dark/30" />
              </div>
              <p className="mt-3 line-clamp-2 text-[15px] font-semibold leading-snug text-brand-dark">
                {b.title}
              </p>
              {b.amount && (
                <p className="mt-2 text-xs font-medium text-brand-dark/60">
                  🎁 {b.amount}
                </p>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* 맞춤 정책 유도 카드 */}
      <section className="mt-7 px-5">
        <div className="rounded-3xl bg-white p-6 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft">
            <Sparkles size={22} className="text-accent" />
          </div>
          <h3 className="mt-4 text-lg font-bold leading-snug text-brand-dark">
            간단한 정보 입력으로
            <br />
            맞춤 정책을 찾아보세요!
          </h3>
          <p className="mt-2 text-sm text-brand-dark/60">
            AI가 사장님의 업종, 규모에 딱 맞는 지원금을 찾아드려요.
          </p>
          <button
            onClick={() => navigate('/onboarding')}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-dark py-3.5 text-base font-semibold text-white active:scale-[0.99]"
          >
            내 정보 입력하기 <ArrowRight size={18} />
          </button>
        </div>
      </section>
    </div>
  )
}
