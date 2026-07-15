// 백엔드 호출 단일 진입점.
// 모든 요청에 JWT를 붙이고, 401이면 토큰을 버리고 로그인으로 보낸다.
// 각 화면이 fetch를 직접 부르면 이 두 가지를 매번 잊게 된다.

// 첨부파일 다운로드처럼 <a href>로 직접 거는 경로도 있어 밖에서 쓸 수 있게 열어둔다.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const TOKEN_KEY = 'sobok.token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // 프라이빗 모드 등 저장 실패는 무시. 이 세션 동안만 로그인 상태가 유지되지 않을 뿐이다.
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // 무시
  }
}

/** 401 응답. 호출부가 로그인 만료를 다른 오류와 구분할 수 있게 별도 타입으로 던진다. */
export class UnauthorizedError extends Error {
  constructor() {
    super('로그인이 만료되었습니다. 다시 로그인해주세요.')
    this.name = 'UnauthorizedError'
  }
}

export class ApiError extends Error {
  status: number
  code: string | null
  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface RequestOptions {
  method?: string
  /** JSON 바디. body와 함께 쓰지 말 것. */
  json?: unknown
  /** FormData 등 raw 바디 (파일 업로드용). Content-Type을 직접 지정하지 않는다. */
  body?: BodyInit
  /** 인증 없이 호출 (로그인 URL 요청 등) */
  anonymous?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', json, body, anonymous = false } = options

  const headers: Record<string, string> = {}
  if (!anonymous) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  if (json !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: json !== undefined ? JSON.stringify(json) : body,
  })

  if (response.status === 401) {
    // 토큰이 만료·위조되었으니 들고 있어봐야 소용없다. 버리고 로그인부터 다시.
    clearToken()
    throw new UnauthorizedError()
  }

  if (!response.ok) {
    const error = await readErrorDetail(response)
    throw new ApiError(response.status, error.message, error.code)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** 인증을 붙인 SSE/스트리밍 응답용 요청. 응답 body는 호출부가 직접 읽는다. */
export async function apiFetchStream(path: string, options: RequestOptions = {}): Promise<Response> {
  const { method = 'GET', json, body, anonymous = false } = options

  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (!anonymous) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  if (json !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: json !== undefined ? JSON.stringify(json) : body,
  })

  if (response.status === 401) {
    clearToken()
    throw new UnauthorizedError()
  }

  if (!response.ok) {
    const error = await readErrorDetail(response)
    throw new ApiError(response.status, error.message, error.code)
  }

  return response
}

async function readErrorDetail(
  response: Response,
): Promise<{ message: string; code: string | null }> {
  try {
    const data = await response.json()
    const detail = (data as { detail?: unknown }).detail
    const errorCode = (data as { error_code?: unknown }).error_code
    if (typeof detail === 'string') {
      return {
        message: detail,
        code: typeof errorCode === 'string' ? errorCode : null,
      }
    }
  } catch {
    // JSON이 아니면 상태 코드만으로 안내한다
  }
  return { message: `요청에 실패했습니다 (HTTP ${response.status})`, code: null }
}
