# SobokSobok Backend

소복소복의 정책 수집·정규화·추천·RAG 상담·서류 검토·캘린더 연동을 담당하는
FastAPI 백엔드입니다.

> 이 문서는 현재 `backend/app`, `docker-compose.yml`, 루트 `.env.example`을 기준으로
> 작성했습니다. 정확한 API 요청·응답 스키마는 실행 중인
> [Swagger UI](http://localhost:8000/docs)를 기준으로 확인하세요.

## 주요 역할

| 영역 | 역할 |
| --- | --- |
| 인증·사용자 | Google OAuth, JWT 인증, 온보딩 프로필, 기능별 AI 모드 저장 |
| 정책 수집 | 소상공인24, SEMAS, 정부24 공고와 첨부파일 수집 |
| 정책 정규화 | 출처별 원문을 공통 정책·문서 스키마로 변환 |
| 추천 | 사업장 프로필 기반 사전 필터링, 벡터 검색, 추천 이유 생성 |
| 정책 상담 | 정책 RAG 검색, 정책별 후속 질문, 대화 기록, SSE 스트리밍 |
| 캘린더 | 저장 정책 마감일 관리, Google Calendar 연동, AI 준비 코칭 |
| 서류 검토 | 업로드 파일 로컬 파싱, 정책 요구 서류 대조, 누락 항목 안내 |

## 기술 구성

- Python 3.11
- FastAPI, SQLAlchemy, Pydantic
- PostgreSQL 16 + pgvector
- OpenAI, Ollama, Gemini
- Google OAuth 2.0, Google Calendar API
- Docker Compose
- `kordoc`, `pdfjs-dist` 기반 첨부파일 텍스트 추출

## 빠른 시작

모든 명령은 프로젝트 루트에서 실행합니다.

### 1. 환경변수 준비

```powershell
Copy-Item .env.example .env
```

최소 설정 항목:

| 환경변수 | 필수 여부 | 용도 |
| --- | --- | --- |
| `DB_PASSWORD` | 필수 | PostgreSQL 비밀번호 |
| `GOOGLE_CLIENT_ID` | 앱 로그인 시 필수 | Google OAuth 클라이언트 ID |
| `GOOGLE_CLIENT_SECRET` | 앱 로그인 시 필수 | Google OAuth 클라이언트 시크릿 |
| `OPENAI_API_KEY` | 클라우드 AI 사용 시 필수 | OpenAI 생성·임베딩 |
| `GOV24_SERVICE_KEY` | 선택 | 정부24 OpenAPI 수집 |
| `OLLAMA_BASE_URL` | 로컬 AI 사용 시 필수 | Ollama 서버 주소 |

환경변수는 프로젝트 루트의 `.env` 한 곳에서 관리합니다.
`backend/.env`는 사용하지 않습니다.

설정 우선순위는 다음과 같습니다.

1. 실행 환경 또는 루트 `.env`
2. `docker-compose.yml`의 Compose 기본값
3. `app/core/config.py`의 애플리케이션 기본값

기능별 모델명과 임베딩 차원은 [루트 `.env.example`](../.env.example)을 확인하세요.

### 2. 백엔드 실행

```bash
docker compose up -d --build db api crawler
```

`api`와 `crawler` 이미지는 코드를 이미지 내부로 복사하므로 코드 변경 후에는
`restart`가 아니라 `--build`가 필요합니다.

```bash
docker compose up -d --build api crawler
```

`.env`를 변경했다면 컨테이너도 다시 생성합니다.

```bash
docker compose up -d --force-recreate api crawler
```

### 3. 상태 확인

```bash
docker compose ps
curl http://localhost:8000/
```

정상 응답:

```json
{
  "message": "Welcome to soboksobok API",
  "docs": "/docs"
}
```

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI JSON: [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json)
- PostgreSQL: `localhost:5431`

## 데이터 처리 파이프라인

`crawler` 컨테이너는 시작 직후 한 번 실행되고, 이후 `CRAWL_INTERVAL_SECONDS` 주기로
같은 작업을 반복합니다. 기본 주기는 24시간입니다.

```text
소상공인24 + SEMAS + 정부24(키가 있을 때)
  → 원천 공고 수집
  → 1차 정책 정규화
  → 첨부파일 본문 추출
  → 추출 성공 시 2차 정규화
  → 채팅·추천·서류검토·발급가이드 벡터 증분 갱신
```

실제 실행 순서는 `app/jobs/crawl_policy_sources_loop.py`가 정의합니다.

1. 소상공인24와 SEMAS를 수집합니다.
2. `GOV24_SERVICE_KEY`가 있으면 정부24도 수집합니다.
3. 공통 정책 스키마로 정규화합니다.
4. 대기 중인 첨부파일을 `kordoc`으로 추출합니다.
5. 새 추출 본문이 생기면 같은 주기 안에서 다시 정규화합니다.
6. 네 벡터 테이블의 신규·변경·누락 데이터만 갱신합니다.

개별 작업을 수동 실행할 수 있습니다.

```bash
# 원천별 1회 수집
docker compose run --rm crawler python -m app.jobs.crawl_sbiz24_once
docker compose run --rm crawler python -m app.jobs.crawl_semas_once
docker compose run --rm crawler python -m app.jobs.crawl_gov24_once

# 정규화·첨부 추출
docker compose run --rm crawler python -m app.jobs.normalize_policies_once
docker compose run --rm crawler python -m app.jobs.extract_attachments_once

# 용도별 벡터 증분 갱신
docker compose exec api python -m app.jobs.embed_policy_chunks_once
docker compose exec api python -m app.jobs.build_rec_vectors_once
docker compose exec api python -m app.jobs.build_review_vectors_once
docker compose exec api python -m app.jobs.build_prep_vectors_once
```

채팅 청크 전체 재생성은 `embed_policy_chunks_once --force`, 서류 검토 벡터 전체
재생성은 `build_review_vectors_once --rebuild`처럼 명시적으로 요청할 때만 수행합니다.

## AI 모델 선택

사용자 프로필에는 아래 기능별 `cloud` 또는 `local` 모드가 저장됩니다.

| 기능 | 신규 사용자 기본 모드 |
| --- | --- |
| 정책 상담 | `cloud` |
| 정책 추천 설명 | `cloud` |
| 정책 상세 요약 | `cloud` |
| 캘린더 AI 코치 | `cloud` |
| 서류 검토 | `local` |

- `cloud`는 OpenAI, `local`은 Ollama를 사용합니다.
- 정책 정규화처럼 사용자와 무관한 배치 작업은
  `NORMALIZATION_LLM_PROVIDER` 설정을 사용하며 OpenAI, Ollama, Gemini를 지원합니다.
- 파일 텍스트 추출은 선택 모드와 관계없이 항상 로컬에서 수행합니다.
- 서류 검토를 `cloud`로 선택하면 로컬에서 파싱된 텍스트가 외부 모델 API로 전달됩니다.

### 이중 임베딩

다음 테이블은 클라우드·로컬 모드 전환을 위해 두 벡터를 별도 컬럼에 저장합니다.

| 용도 | 테이블 |
| --- | --- |
| 정책 상담 | `policy_chunks` |
| 정책 추천 | `rec_vectors` |
| 요구 서류 검색 | `review_vectors` |
| 서류 발급 가이드 | `prep_vectors` |

- `embedding_openai`: 기본 1536차원
- `embedding_ollama`: 기본 1024차원

모델명과 차원은 기능별 환경변수가 단일 기준입니다. 두 벡터는 같은 컬럼에 섞이지 않으며,
원문 해시·모델명·벡터 상태가 달라진 항목만 다시 생성합니다.

## API 구성

모든 v1 API의 공통 prefix는 `/api/v1`입니다.

| Prefix | 주요 기능 |
| --- | --- |
| `/auth` | Google 로그인 URL, OAuth 콜백, 인증 테스트 |
| `/users` | 내 계정·프로필 조회와 온보딩/AI 설정 저장 |
| `/favorites` | 저장한 정책 조회·추가·삭제 |
| `/policies` | 원천/정규화 정책 목록·상세·첨부파일 다운로드 |
| `/recommend` | 프로필 기반 추천과 추천 설명 |
| `/chat` | 검색, 일반·스트리밍 질문, 대화 기록, 정책 선택 |
| `/calendar` | 일정 등록·조회·삭제, AI 신청 준비 코치 |
| `/review` | 서류 검토 시작, 진행 상태와 결과 폴링 |

### 정책 상담

- 전체 정책 질문은 사용자 모드와 같은 임베딩 컬럼에서 후보를 찾습니다.
- 사용자가 정책을 선택한 뒤의 후속 질문은 해당 정책의 `policy_documents`를 근거로 사용합니다.
- `POST /api/v1/chat/ask/stream`은 검색 근거와 답변 토큰을 SSE로 반환합니다.
- 대화와 근거 메타데이터는 `chat_sessions`, `chat_messages`에 저장됩니다.

### 캘린더

- Google Calendar 일정 등록 시 정책의 실제 `apply_end`를 마감일로 사용합니다.
- AI 코치의 선택적 `target_date`는 오늘 이후이면서 실제 마감일 이전이어야 합니다.
- 일정 0건과 Google API 권한·통신·시간 초과 오류를 구분합니다.
- 일정 CRUD에는 LLM을 사용하지 않고, 준비 코칭에만 LLM과 발급 가이드 RAG를 사용합니다.

### 서류 검토

- 업로드 직후 검토 세션을 만들고 백그라운드 작업을 시작합니다.
- 클라이언트는 `GET /api/v1/review/{session_id}`를 폴링해 진행 상태와 결과를 받습니다.
- 업로드 원문은 공유 `review_vectors`에 저장하거나 공용 임베딩 대상으로 사용하지 않습니다.
- 파일당 기본 업로드 제한은 20MB이며, 검토 모델 제한시간 기본값은 180초입니다.

## 데이터베이스

### 연결

Compose 내부:

```text
Host: db
Port: 5432
Database: soboksobok
Username: edu
Password: .env의 DB_PASSWORD
```

호스트/DBeaver:

```text
Host: localhost
Port: 5431
Database: soboksobok
Username: edu
Password: .env의 DB_PASSWORD
```

`DATABASE_URL`을 설정하면 개별 DB 환경변수보다 우선합니다.

### 테이블 구분

| 구분 | 주요 테이블 |
| --- | --- |
| 원천 데이터 | `policy_announcements`, `policy_attachments`, `policy_program_pages`, `gov24_*` |
| 정규화 데이터 | `normalized_policies`, `policy_documents`, `attachment_files`, `policy_attachment_links` |
| 벡터 데이터 | `policy_chunks`, `rec_vectors`, `review_vectors`, `prep_vectors` |
| 사용자 데이터 | `users`, `user_profiles`, `favorites` |
| 상담·검토 | `chat_sessions`, `chat_messages`, `review_sessions`, `review_uploads` |

API 시작 시 다음 초기화가 자동으로 실행됩니다.

1. `vector` 확장을 생성합니다.
2. 호환되지 않는 레거시 사용자·검토 스키마를 정리합니다.
3. SQLAlchemy 모델 테이블을 생성합니다.
4. 누락 컬럼·인덱스·제약조건을 보완합니다.

별도의 수동 마이그레이션 명령은 현재 없습니다.

> `docker compose down -v`는 회원·정책·대화를 포함한 로컬 PostgreSQL 볼륨을
> 삭제합니다. 초기화가 명확히 필요한 경우에만 사용하세요.

## 프로젝트 구조

```text
backend/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── api/
│   │   ├── api.py                # v1 라우터 조합
│   │   └── v1/                   # auth, users, favorites, policies,
│   │                             # recommend, chat, calendar, review
│   ├── core/                     # 설정, DB, 인증, 모델 공급자, 공통 오류
│   ├── crawlers/                 # Gov24, Sbiz24, SEMAS HTTP 클라이언트
│   ├── crud/                     # 정책 조회 CRUD
│   ├── jobs/                     # 수집·정규화·추출·임베딩 실행 진입점
│   ├── models/                   # SQLAlchemy 모델과 스키마 보완
│   ├── schemas/                  # API 요청·응답 모델
│   ├── services/
│   │   ├── normalization/        # 출처별 공통 정책 정규화
│   │   ├── chat_graph.py         # 정책 상담 상태 흐름
│   │   ├── chat_history.py       # 대화 기록
│   │   ├── chat_rag.py           # 청킹·검색·답변 생성
│   │   ├── recommend.py          # 추천 필터·벡터 검색·설명
│   │   ├── review_documents.py   # 업로드 서류 검토
│   │   ├── extract_attachments.py
│   │   └── prep_rag.py           # 발급 가이드 검색
│   └── main.py                   # FastAPI 앱과 DB 초기화
├── storage/                      # 첨부파일·검토 업로드 로컬 저장
└── tests/                        # pytest 회귀·품질 테스트
```

## 테스트

프로젝트 루트에서 현재 소스를 컨테이너에 마운트해 실행합니다.

```bash
docker compose run --rm -T -v ./backend:/app api python -m pytest -q
```

주요 테스트만 선택할 수도 있습니다.

```bash
docker compose run --rm -T -v ./backend:/app api \
  python -m pytest tests/test_calendar.py tests/test_recommend_api.py -q
```

정규화 골드셋 품질 측정:

```bash
docker compose run --rm crawler python -m app.jobs.evaluate_normalization_quality
```

## 로그와 문제 해결

```bash
docker compose logs -f api
docker compose logs -f crawler
```

- 코드 변경이 반영되지 않으면 `docker compose up -d --build api crawler`를 실행합니다.
- `.env` 변경이 반영되지 않으면 `--force-recreate`로 컨테이너를 다시 만듭니다.
- Google 로그인 오류는 `GOOGLE_REDIRECT_URI`가 Google Cloud Console의 승인된
  리디렉션 URI와 같은지 확인합니다.
- Ollama 연결 오류는 호스트에서 `ollama list`와
  `OLLAMA_BASE_URL=http://host.docker.internal:11434`를 확인합니다.
- 모델 호출 로그에는 기본적으로 프롬프트·응답 원문·벡터·API 키·원본 파일명을 남기지 않습니다.
