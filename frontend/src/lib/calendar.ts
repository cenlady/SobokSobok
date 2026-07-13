// 날짜 유틸.
//
// 구글 캘린더 등록은 더 이상 여기서 URL을 조립하지 않는다. 예전에는 구글의 "일정 추가"
// 화면을 새 탭으로 여는 TEMPLATE URL을 만들었고, 사용자가 그 탭에서 '저장'을 한 번 더
// 눌러야 실제로 등록됐다. 이제 서버가 Calendar API로 직접 등록한다.
// → components/AddToCalendarButton.tsx, POST /api/v1/calendar/event

export function localDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function toDateKey(value?: string | null) {
  if (!value) return null
  return value.slice(0, 10)
}

export function formatDate(value?: string | null) {
  const dateKey = toDateKey(value)
  return dateKey ? dateKey.replaceAll('-', '.') : '미정'
}

export function addDays(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T00:00:00`)
  date.setDate(date.getDate() + days)
  return localDateKey(date)
}
