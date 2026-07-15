interface BrandMarkProps {
  size?: number
  framed?: boolean
  className?: string
}

/**
 * 소복소복 브랜드 마크.
 *
 * 뒤로 겹쳐진 세 장의 카드는 여러 기관의 지원 정책이 한곳에 모이는 모습을,
 * 오른쪽 위의 반짝임은 조건에 맞는 정책을 발견하는 순간을 뜻한다.
 */
export default function BrandMark({
  size = 56,
  framed = true,
  className = '',
}: BrandMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center ${
        framed ? 'rounded-[18px] border border-line bg-surface shadow-card' : ''
      } ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={framed ? size * 0.68 : size}
        height={framed ? size * 0.68 : size}
        viewBox="0 0 48 48"
        fill="none"
      >
        <rect x="14" y="8" width="25" height="26" rx="7" fill="#FCE9CC" />
        <rect x="9" y="13" width="29" height="26" rx="7" fill="#F5A623" fillOpacity="0.52" />
        <rect x="8.75" y="17.75" width="28.5" height="22.5" rx="6.25" fill="#FFFDF9" />
        <rect
          x="8.75"
          y="17.75"
          width="28.5"
          height="22.5"
          rx="6.25"
          stroke="#8B5E1C"
          strokeWidth="1.5"
        />
        <path d="M16 25H30" stroke="#8B5E1C" strokeWidth="2" strokeLinecap="round" />
        <path d="M16 31H25" stroke="#C2410C" strokeWidth="2" strokeLinecap="round" />
        <path d="M39.5 6.5V12.5" stroke="#C2410C" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M36.5 9.5H42.5" stroke="#C2410C" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </span>
  )
}
