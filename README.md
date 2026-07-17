# SobokSobok

소상공인 지원사업 공고를 수집하고, 사용자에게 정책/혜택 정보를 제공하기 위한 서비스입니다.

## 현재 제공 기능

- 소상공인24·SEMAS·Gov24 정책 수집, 첨부파일 본문 추출, 공통 정책 스키마 정규화
- 사업장 프로필 기반 정책 추천과 저장한 정책의 마감일 캘린더 표시
- 전체 정책 벡터 검색, 정책 선택 후 부모 문서 기반 후속 질문, SSE 스트리밍 채팅
- Google Calendar 일정 등록·조회와 실제 정책 마감일 기반 AI 신청 준비 코칭
- 제출 서류 로컬 파싱, 정책 요건 대조, 자주 쓰는 서류의 발급 가이드 검색
- 챗봇·추천·정책 요약·캘린더 코치·서류검토별 cloud/local 모델 선택

신규 온보딩의 활동지역 기본값은 `서울특별시 전체`입니다. `전체`는 특정 구로 제한하지
않는다는 뜻이며, 저장 시 시도는 `서울특별시`, 시군구는 제한 없음으로 처리합니다.

## 실행 방법

### 0. 사전 준비

- **Docker Desktop** 실행 중일 것
- **Node.js 20+**
- 로컬 AI 또는 서류검토를 사용할 PC에서는 **Ollama** 실행 중 + 모델 2개 설치

```bash
ollama pull bge-m3        # 로컬 검색 + 서류검토 임베딩 (1024차원)
ollama pull exaone3.5     # 로컬 챗/추천/캘린더 코치 + 서류검토 진단
ollama list               # 두 개 다 보이면 OK
```

> 기본 사용자 설정은 `클라우드 AI(OpenAI)`입니다. 다만 서류검토는 개인정보 보호를
> 위해 기본적으로 Ollama만 사용하므로, 서류검토 기능에는 Ollama가 필요합니다.

### 1. `.env` 만들기

```bash
cp .env.example .env
```

**`.env`에 키를 채워 넣으세요. 값은 팀장에게 받으세요.** (`.env`는 커밋 금지)

| 키 | 없으면 |
| --- | --- |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | **로그인이 안 돼 앱을 아예 못 씁니다** |
| `OPENAI_API_KEY` | 기본 클라우드 AI와 정책 정규화가 동작하지 않습니다 |
| `GEMINI_API_KEY` | `.env`에서 Gemini provider를 선택한 기능만 동작하지 않습니다 |

### AI 모델 선택과 기본값

마이페이지의 `AI 기능 설정`에서 기능별로 `클라우드 AI` 또는 `로컬 AI`를 선택할 수 있습니다.

| 기능 | 기본/클라우드 AI | 로컬 AI | 비고 |
| --- | --- | --- | --- |
| 챗봇 | OpenAI `gpt-5.4-mini` | Ollama `exaone3.5` | 사용자 프로필 선택 적용 |
| 정책 추천 설명 | OpenAI `gpt-5.4-mini` | Ollama `exaone3.5` | 사용자 프로필 선택 적용 |
| 정책 상세 요약 | OpenAI `gpt-4o-mini` | Ollama `exaone3.5` | 사용자 프로필 선택 적용 |
| 정책 정규화 | OpenAI `gpt-5.4-nano` | `.env`로 변경 가능 | 사용자와 무관한 배치 작업 |
| 캘린더 AI 코치 | OpenAI `gpt-5-mini` | Ollama `exaone3.5` | 캘린더 CRUD에는 LLM 미사용 |
| 서류검토 | OpenAI `gpt-5.4-mini` | Ollama `exaone3.5` | 프로필 기본값은 로컬, 파일 파싱은 항상 로컬 |

챗봇·추천·서류 요건·서류 발급 가이드 검색은 사용자 선택을 즉시 바꿀 수 있도록 두 임베딩을 모두 저장합니다.
OpenAI `text-embedding-3-small` 1536차원과 Ollama `bge-m3` 1024차원은 각각 별도
pgvector 컬럼에 저장되며 같은 컬럼에 섞이지 않습니다. 기능별 상세 변수와 변경 가능한
모델 예시는 [`.env.example`](./.env.example)의 주석을 확인하세요.

각 테이블은 `embedding_openai`와 `embedding_ollama`만 사용하며 레거시 `embedding` 컬럼은
사용하지 않습니다. 크롤러는 시작 직후와 매 수집 주기마다 원문·모델·벡터 상태를 비교해
신규·변경·누락 데이터만 임베딩합니다. 값이 같으면 OpenAI/Ollama 호출을 하지 않습니다.

### 채팅과 캘린더 동작 원칙

- 전체 정책 채팅은 사용자 모드와 같은 벡터 컬럼으로 후보를 검색합니다. 정책이 선택된
  후속 질문은 임베딩 검색 대신 해당 정책의 `policy_documents` 부모 문서를 읽습니다.
- 일반 응답과 SSE 스트리밍 응답은 같은 정책 문맥·후보 선택·집중 속성 답변 로직을 사용합니다.
- 캘린더 코치는 `normalized_policies.apply_end`를 실제 마감일로 고정합니다. 선택적인
  `target_date`는 오늘부터 실제 마감일까지의 준비 완료 목표일로만 허용합니다.
- Google Calendar의 정상적인 일정 0건과 권한·통신·시간 초과 오류를 구분합니다. 조회 실패를
  빈 일정으로 바꿔 AI에게 전달하지 않습니다.
- 캘린더 코치는 사용자 cloud/local 설정에 맞는 `prep_vectors` 발급 가이드와 같은 모드의
  채팅 모델을 사용합니다. 캘린더 일정 등록·조회 자체에는 LLM을 사용하지 않습니다.

```bash
docker compose up -d --build --force-recreate api crawler
```

자동 작업을 기다리지 않고 증분 작업을 수동 실행할 때도 기본값은 변경분 처리입니다.

```bash
docker compose exec api python -m app.jobs.embed_policy_chunks_once
docker compose exec api python -m app.jobs.build_rec_vectors_once
docker compose exec api python -m app.jobs.build_review_vectors_once
docker compose exec api python -m app.jobs.build_prep_vectors_once
```

채팅 청크 전체 재생성은 `embed_policy_chunks_once --force`, 검토 벡터 전체 재생성은
`build_review_vectors_once --rebuild`처럼 명시적으로 요청할 때만 수행합니다.

개발 DB를 새 스키마로 완전히 다시 만들 때는 코드 변경 후 `docker compose down -v`를
실행합니다. 이 명령은 회원·정책·채팅을 포함한 PostgreSQL 데이터를 모두 삭제합니다.

### 2. 백엔드 (Docker)

```bash
docker compose up -d --build
```

- `--build`는 **필수**입니다. `Dockerfile`이 코드를 이미지에 굽기 때문에(`COPY app ./app`),
  `docker compose restart`로는 새 코드가 반영되지 않습니다.
- **`.env`를 수정했다면** 컨테이너를 다시 만들어야 합니다. 환경변수는 컨테이너 생성 시점에
  주입되므로 `restart`로는 갱신되지 않습니다.

```bash
docker compose up -d --force-recreate api
```

확인:

```bash
curl http://localhost:8000/          # {"message": "Welcome to soboksobok API"}
```

- API 문서: http://localhost:8000/docs
- 스키마 마이그레이션은 **서버 기동 시 자동**으로 돕니다. 별도 명령이 없습니다.

### 3. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

- **반드시 포트 5173에서 떠야 합니다.** 구글 로그인 콜백이 `http://localhost:5173/auth/callback`
  으로 돌아오기 때문입니다. 다른 포트면 로그인이 끊깁니다.
- 5173이 이미 쓰이고 있으면 Vite가 5174로 넘어갑니다. 그 경우 기존 프로세스를 먼저 종료하세요.

👉 **http://localhost:5173**

### 4. 첫 진입 흐름

```
로그인 화면 → Google로 시작하기 → 구글 동의
  → 온보딩 (프로필 입력)  ← 신규 계정은 반드시 거칩니다
  → 홈 (달력)
```

### 5. 변경사항 검증

백엔드 전체 테스트는 현재 소스를 API 이미지에 마운트해 실행합니다.

```bash
docker compose run --rm -T -v ./backend:/app api python -m pytest -q
```

프론트엔드는 정적 검사와 프로덕션 빌드를 모두 확인합니다.

```bash
cd frontend
npm run lint
npm run build
```

---

## 구글 로그인이 안 될 때

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| 로그인 버튼을 눌러도 아무 일 없음 | `.env`에 `GOOGLE_CLIENT_ID`/`SECRET`이 비어 있음 | 값을 채우고 `docker compose up -d --force-recreate api` |
| 동의 후 **JSON 화면**이 뜸 | 옛 코드 (콜백이 JSON을 반환) | 최신 브랜치를 받고 `docker compose up -d --build` |
| 동의 후 500 에러 | `users` 테이블에 구글 토큰 컬럼이 없음 | 최신 브랜치를 받고 `docker compose up -d --build` (기동 시 자동 패치) |
| `redirect_uri_mismatch` | 구글 콘솔 설정 문제 | 콘솔에 `http://localhost:8000/api/v1/auth/google/callback` 등록 확인 |
| 동의 후 빈 화면 | 프론트가 5173이 아님 | 5173으로 다시 띄우기 |

**진단 명령**

```bash
# 구글 키가 컨테이너에 주입됐는지
docker compose exec api python -c "from app.core.config import settings; print('ID:', bool(settings.GOOGLE_CLIENT_ID), '/ SECRET:', bool(settings.GOOGLE_CLIENT_SECRET))"

# 로그인 URL이 정상 생성되는지 (500이면 키 문제)
curl http://localhost:8000/api/v1/auth/google/login-url
```

## 로그가 보고 싶을 때

```bash
docker compose logs -f api        # 백엔드
docker compose logs -f crawler    # 크롤러
```

모델 호출은 다음처럼 한 줄 메타데이터로 출력됩니다.

```text
model_call service=api feature=chat task=chat stage=answer_generation provider=openai model=gpt-5.4-mini source=app.services.chat_rag:generate_chat_answer input_type=text input_count=1 input_chars=1820 output_chars=420 result_count=1 dimensions=- latency_ms=812 status=success retry_count=0 error_type=-
```

프롬프트·응답 원문·벡터·API 키·토큰·원본 파일명은 로그에 기록하지 않습니다.

### AI 호출 실패 처리

- 채팅/추천 설명/캘린더 AI 코치는 모델 연결 실패 시 임의의 정적 답변으로 대체하지 않습니다.
- 연결 실패는 HTTP 502, 설정 오류는 503, 시간 초과는 504로 응답하며 `error_code`와 안전한 한국어 안내를 함께 반환합니다.
- 비동기 서류검토 실패는 폴링 응답의 `review_status=failed`, `error_code`, `summary`로 확인합니다. SDK 오류 원문이나 개인정보는 저장·응답하지 않습니다.
- `LLM_REQUEST_TIMEOUT_SECONDS`와 `LLM_EMBEDDING_TIMEOUT_SECONDS`로 공통 제한시간을 조정할 수 있습니다. 정규화와 서류검토는 각각 `NORMALIZE_LLM_TIMEOUT_SECONDS`, `REVIEW_LLM_TIMEOUT_SECONDS`가 우선합니다.
- Google Calendar 권한 오류는 401/403, 외부 API 연결 실패는 502, 시간 초과는 504로 응답합니다. 오류가 발생한 캘린더를 일정 0건으로 처리하지 않습니다.
