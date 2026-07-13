# SobokSobok

소상공인 지원사업 공고를 수집하고, 사용자에게 정책/혜택 정보를 제공하기 위한 서비스입니다.

## 실행 방법

### 0. 사전 준비

- **Docker Desktop** 실행 중일 것
- **Node.js 20+**
- **Ollama** 실행 중 + 모델 2개 설치

```bash
ollama pull bge-m3        # 임베딩 (추천·챗봇·서류검토 전부 사용)
ollama pull exaone3.5     # 서류검토 진단 LLM
ollama list               # 두 개 다 보이면 OK
```

> Ollama가 안 떠 있으면 추천·챗봇·서류검토가 전부 실패합니다.

### 1. `.env` 만들기

```bash
cp .env.example .env
```

**`.env`에 키를 채워 넣으세요. 값은 팀장에게 받으세요.** (`.env`는 커밋 금지)

| 키 | 없으면 |
| --- | --- |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | **로그인이 안 돼 앱을 아예 못 씁니다** |
| `OPENAI_API_KEY` | 챗봇이 답변을 못 만듭니다 |
| `GEMINI_API_KEY` | 정책 상세 AI 요약이 규칙 기반으로 폴백 (에러는 아님) |

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
