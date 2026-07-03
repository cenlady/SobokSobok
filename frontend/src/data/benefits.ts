import type { Benefit } from '../types'

// 목업 혜택 데이터 (실제 API 대체용)
export const benefits: Benefit[] = [
  {
    id: 'elec-2024',
    title: '소상공인 전기요금 특별지원',
    summary: '사업장 당 최대 20만원 전기요금 감면 지원',
    status: 'closing',
    amount: '최대 20만원',
    dueDate: '2024-06-17',
    category: '공과금',
    region: '전국',
    timeLabel: '오후 6시까지',
    content:
      '고물가·고금리로 어려움을 겪는 소상공인의 경영 부담을 덜기 위해 사업장 당 최대 20만원의 전기요금을 감면 지원합니다. 2024년 상반기 기준 전기요금 납부 내역이 있는 사업자라면 누구나 신청할 수 있습니다.',
  },
  {
    id: 'noran-2024',
    title: '노란우산공제 가입 장려금',
    summary: '신규 가입 시 지자체별 최대 2만원 추가 지원',
    status: 'open',
    amount: '최대 2만원',
    dueDate: '2024-06-17',
    startDate: '2024-06-17',
    category: '공제/보험',
    region: '전국',
    timeLabel: 'D-Day',
    content:
      '소기업·소상공인의 생활 안정과 사업 재기를 돕는 노란우산공제에 신규 가입하는 사장님께 지자체별로 최대 2만원의 장려금을 추가 지원합니다.',
  },
  {
    id: 'digital-2024',
    title: '디지털 전환 바우처 공고',
    summary: '스마트 상점 구축 비용 지원사업 2차 공고',
    status: 'notice',
    dueDate: '2024-06-17',
    category: '디지털',
    region: '전국',
    timeLabel: '오전 10시',
    content:
      '오프라인 매장의 디지털 전환을 지원하기 위한 스마트 상점 구축 비용 지원사업 2차 공고입니다. 키오스크, 테이블 오더, 스마트 결제 등 도입 비용의 일부를 바우처 형태로 지원합니다.',
  },
  {
    id: 'hvac-2024',
    title: '2024년 영세 소상공인 냉난방기 교체 지원',
    summary: '노후 냉난방기 교체 비용 최대 300만원 지원',
    status: 'open',
    amount: '최대 300만원',
    dueDate: '2024-05-31',
    startDate: '2024-05-01',
    endDate: '2024-05-31',
    category: '음식점업',
    region: '전국',
    content:
      '에너지 효율이 낮은 노후 냉난방기를 고효율 제품으로 교체하는 영세 소상공인에게 교체 비용을 최대 300만원까지 지원합니다. 음식점업 사장님께 특히 유리한 지원사업입니다.',
  },
  {
    id: 'tax-2024',
    title: '부가가치세 예정신고 안내',
    summary: '1기 예정 부가가치세 신고·납부 기간 안내',
    status: 'notice',
    dueDate: '2024-06-25',
    category: '세무',
    region: '전국',
    timeLabel: '오전 9시',
    content: '2024년 제1기 예정 부가가치세 신고·납부 기간입니다. 기한 내 신고하여 가산세를 피하세요.',
  },
]

export function getBenefit(id: string) {
  return benefits.find((b) => b.id === id)
}

// 특정 날짜(YYYY-MM-DD)에 해당하는 혜택
export function benefitsOnDate(date: string) {
  return benefits.filter((b) => b.dueDate === date)
}
