import BrandMark from './BrandMark'

/**
 * 상단 공통 헤더.
 *
 * 로고를 작게 뒀다. 매 화면에 있는 요소는 조용해야 한다. 예전에는 로고가 페이지
 * 타이틀과 같은 크기(text-2xl)라 서로 싸웠고, 그래서 화면마다 "여기가 어디인지"가
 * 흐릿했다. 이제 위계는 [페이지 타이틀 26px] > [로고 19px] 순이다.
 */
export default function TopBar() {
  return (
    <header className="sticky top-0 z-10 flex items-center bg-cream/90 px-5 py-3.5 backdrop-blur">
      <div className="flex items-center gap-2">
        <BrandMark size={27} framed={false} />
        <span className="text-[19px] font-extrabold tracking-tight text-brand">소복소복</span>
      </div>
    </header>
  )
}
