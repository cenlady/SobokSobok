interface BrandMarkProps {
  size?: number
  framed?: boolean
  className?: string
}

/**
 * 소복소복 브랜드 마크.
 *
 * 위쪽 두 집게는 정책 마감일을 걸어두는 달력을, 아래 세 점 중 하나가 켜진 모습은
 * 조건에 맞는 정책을 발견해 챙기는 순간을 뜻한다. favicon과 동일한 디자인이다.
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
        viewBox="0 0 96 96"
        fill="none"
      >
        <rect x="14" y="24" width="68" height="58" rx="14" fill="#C2410C" />
        <path
          d="M14 44 C 24 34, 36 46, 48 40 C 60 34, 72 46, 82 40 L 82 68 C 82 75.7 75.7 82 68 82 L 28 82 C 20.3 82 14 75.7 14 68 Z"
          fill="#FFFDF9"
        />
        <rect x="28" y="14" width="10" height="18" rx="5" fill="#8B5E1C" />
        <rect x="58" y="14" width="10" height="18" rx="5" fill="#8B5E1C" />
        <circle cx="34" cy="60" r="4.5" fill="#F5A623" />
        <circle cx="48" cy="64" r="4.5" fill="#E3DBD1" />
        <circle cx="62" cy="60" r="4.5" fill="#E3DBD1" />
      </svg>
    </span>
  )
}
