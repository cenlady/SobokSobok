import { NEED_OPTIONS } from './recommend'

const SUPPORT_TYPE_LABELS: Record<string, string> = {
  현금: '현금 지원',
  비현금: '서비스 지원',
  현물: '현물 지원',
  융자: '융자',
  보조금: '보조금',
  기술지원: '기술 지원',
}

function getSupportTypeLabels(value: string) {
  const tokens = value
    .replace(/\*+/g, ' ')
    .replace(/기타\s*\(([^)]*)\)/g, ' $1 ')
    .split(/[,/|·;\s]+/)
    .map((token) => token.trim())
    .filter(Boolean)

  return tokens
    .filter((token) => token !== '기타')
    .map((token) => SUPPORT_TYPE_LABELS[token] || token)
    .filter((token) => token.length <= 12)
}

export function getPolicyLabels(policy: {
  categories?: string[]
  support_type?: string | null
}) {
  const labels = [
    ...(policy.categories || []).map(
      (category) => NEED_OPTIONS.find((option) => option.tag === category)?.label || category,
    ),
    ...(policy.support_type ? getSupportTypeLabels(policy.support_type) : []),
  ]

  return labels.filter((label, index) => labels.indexOf(label) === index)
}
