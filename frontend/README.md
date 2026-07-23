# SobokSobok Frontend

소복소복의 정책 탐색·추천·달력·AI 상담·서류 검토 화면을 제공하는 React 웹
애플리케이션입니다.

> 이 문서는 현재 `frontend/src`, `frontend/package.json`, `frontend/Dockerfile`을
> 기준으로 작성했습니다. 전체 서비스 소개와 실행 화면은 [루트 README](../README.md)를
> 확인하세요.

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| UI | React 19, TypeScript 6 |
| Build | Vite 8 |
| Styling | Tailwind CSS 3 |
| Routing | React Router 7 |
| Icons | Lucide React |
| Lint | Oxlint |
| Production | Nginx 1.27 |

## 개발 환경 요구사항

- Node.js `^20.19.0` 또는 `>=22.12.0`
- npm
- 실행 중인 SobokSobok API

Vite 8의 Node 엔진 요구사항 때문에 Node 18에서는 설치 또는 빌드가 실패할 수 있습니다.
Docker 이미지는 Node 20으로 빌드합니다.

## 빠른 시작

### 전체 서비스를 Docker로 실행

프로젝트 루트에서 실행합니다.

```bash
docker compose up -d --build
```

프론트엔드: [http://localhost:5173](http://localhost:5173)

### 프론트엔드만 로컬 개발

먼저 프로젝트 루트에서 백엔드를 실행합니다.

```bash
docker compose up -d --build db api crawler
```

그다음 프론트엔드 개발 서버를 실행합니다.

```bash
cd frontend
npm ci
npm run dev
```

Google OAuth 완료 후 백엔드가 `http://localhost:5173/auth/callback`으로 사용자를
돌려보내므로 개발 서버는 `5173` 포트를 사용해야 합니다. 이미 사용 중인 포트가 있으면
Vite가 자동으로 다른 포트를 선택할 수 있으니 터미널 출력도 확인하세요.

## 환경변수

프론트엔드에서 사용하는 환경변수는 하나입니다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | 백엔드 API 주소 |

`VITE_API_BASE_URL`은 브라우저 런타임이 아니라 **빌드 시점**에 번들에 포함됩니다.

- 로컬 Vite는 쉘 환경 또는 Vite 환경 파일의 값을 읽습니다.
- Docker 빌드는 루트 `.env` 값을 Compose build argument로 전달합니다.
- 값을 바꾼 뒤에는 프론트엔드 이미지를 다시 빌드해야 합니다.

```bash
docker compose up -d --build frontend
```

## 화면과 라우트

| 경로 | 화면 | 인증 |
| --- | --- | --- |
| `/login` | Google 로그인 | 불필요 |
| `/auth/callback` | OAuth 결과 처리 | 불필요 |
| `/onboarding` | 사업장 프로필 등록·수정 | 필요 |
| `/welcome` | 온보딩 완료 안내 | 필요 |
| `/` | 저장 정책 달력과 신청 준비 코치 | 필요 |
| `/policies` | 추천·저장·전체 정책 탐색 | 필요 |
| `/policy/:policyId` | 정책 상세, 추천 근거, 요약 | 필요 |
| `/review` | 제출 서류 업로드와 비동기 검토 | 필요 |
| `/chat` | 정책 RAG 상담과 대화 기록 | 필요 |
| `/profile` | 프로필과 계정 정보 | 필요 |
| `/profile/ai-settings` | 기능별 클라우드·로컬 AI 설정 | 필요 |

하단 내비게이션은 홈, 정책 찾기, 서류검토, 도우미, 마이의 다섯 탭으로 구성됩니다.
정책 상세와 AI 설정 화면은 하단 탭 없이 독립 화면으로 표시됩니다.

## 인증 흐름

```text
/login
  → 백엔드에서 Google 로그인 URL 요청
  → Google OAuth
  → 백엔드 /api/v1/auth/google/callback
  → /auth/callback?token=...
  → /api/v1/users/me
  → 미온보딩: /onboarding
  → 온보딩 완료: /welcome 또는 요청한 보호 화면
```

- JWT는 `localStorage`의 `sobok.token` 키에 저장됩니다.
- `apiFetch`와 `apiFetchStream`이 인증 헤더를 공통으로 추가합니다.
- API가 `401`을 반환하면 토큰을 삭제하고 로그인 상태를 해제합니다.
- `RequireAuth`가 미로그인 사용자를 `/login`, 미온보딩 사용자를 `/onboarding`으로
  이동시킵니다.

## 주요 화면 동작

### 홈

- 저장한 정책의 접수 마감일을 월간 달력으로 표시합니다.
- Google Calendar 일정 등록·해제를 반영합니다.
- 정책 마감일과 개인 일정을 바탕으로 AI 신청 준비 가이드를 표시합니다.

### 정책 찾기

- `추천`, `저장한`, `전체` 탭을 제공합니다.
- 키워드, 신청 기간, 정렬 조건을 사용해 정책을 탐색합니다.
- 추천 정책에는 점수와 사용자 조건에 맞는 이유를 표시합니다.

### 정책 도우미

- 전체 정책 질문과 특정 정책 후속 질문을 지원합니다.
- `apiFetchStream`으로 SSE 응답을 읽어 답변을 실시간 표시합니다.
- 정책 후보, 답변 근거, 추천 후속 질문, 서버 대화 기록을 제공합니다.
- 현재 대화 세션 ID와 선택 정책은 화면 복원을 위해 로컬 저장소에 보관합니다.

### 서류 검토

- 저장 정책을 선택하거나 정책 없이 서류만 검토할 수 있습니다.
- PDF, HWP, DOCX, XLSX 파일을 최대 10개까지 선택합니다.
- 검토 세션을 만든 뒤 상태 API를 폴링해 진행률과 결과를 표시합니다.
- 진행 중인 검토 정보는 새로고침 복원을 위해 로컬 저장소에 보관합니다.

## API 호출 구조

`src/lib/api.ts`가 백엔드 호출의 단일 진입점입니다.

```text
apiFetch        JSON·FormData 요청, JWT 추가, 공통 오류 처리
apiFetchStream  SSE 요청, JWT 추가, 스트리밍 Response 반환
ApiError        HTTP 상태와 백엔드 error_code 전달
UnauthorizedError
                401을 일반 API 오류와 구분
```

화면 컴포넌트에서 새로운 API를 연결할 때는 직접 `fetch`를 호출하기보다 이 공통 함수를
사용합니다.

## 프로젝트 구조

```text
frontend/
├── public/                       # 파비콘과 SVG 아이콘
├── src/
│   ├── assets/                   # 캐릭터·이미지 에셋
│   ├── components/
│   │   ├── AppLayout.tsx         # 공통 프레임
│   │   ├── TopBar.tsx            # 상단 바
│   │   ├── BottomNav.tsx         # 하단 다섯 탭
│   │   ├── RequireAuth.tsx       # 로그인·온보딩 가드
│   │   ├── PolicyCard.tsx        # 정책 카드
│   │   ├── ChatHistoryDrawer.tsx # 대화 기록 패널
│   │   └── ui.tsx                # 공통 UI 요소
│   ├── lib/
│   │   ├── api.ts                # API·JWT·오류 처리
│   │   ├── auth.tsx              # 전역 인증 상태
│   │   ├── calendar.ts           # 일정 API
│   │   ├── profile.ts            # 프로필 API
│   │   ├── recommend.ts          # 추천 API
│   │   └── *.ts                  # 날짜·라벨·텍스트 유틸리티
│   ├── screens/                  # 라우트별 화면
│   ├── App.tsx                   # 라우트 정의
│   ├── main.tsx                  # React 진입점
│   ├── index.css                 # Tailwind·전역 스타일
│   └── types.ts                  # 공통 API·UI 타입
├── Dockerfile                    # Node 빌드 → Nginx 런타임
├── nginx.conf                    # SPA fallback·정적 자원 캐시
├── package.json
└── vite.config.ts
```

## npm 스크립트

| 명령 | 설명 |
| --- | --- |
| `npm run dev` | Vite 개발 서버 실행 |
| `npm run build` | TypeScript 프로젝트 빌드 후 프로덕션 번들 생성 |
| `npm run lint` | Oxlint 정적 검사 |
| `npm run preview` | 빌드 결과 로컬 미리보기 |

## 검증

```bash
cd frontend
npm run lint
npm run build
```

프로덕션 Docker 이미지까지 확인하려면 프로젝트 루트에서 실행합니다.

```bash
docker compose build frontend
docker compose up -d frontend
```

직접 URL로 새로고침해도 Nginx의 SPA fallback 설정 때문에 React Router 화면이 정상적으로
열려야 합니다.

## 문제 해결

- **로그인 후 빈 화면**: 프론트엔드가 `5173` 포트인지 확인합니다.
- **API 연결 실패**: `VITE_API_BASE_URL`과 API 컨테이너 상태를 확인합니다.
- **환경변수 변경 미반영**: `docker compose up -d --build frontend`로 다시 빌드합니다.
- **Node 엔진 오류**: Node `20.19+` 또는 `22.12+`로 업그레이드합니다.
- **직접 경로 새로고침 404**: 로컬 개발 서버 또는 제공된 `nginx.conf`로 실행 중인지
  확인합니다.
