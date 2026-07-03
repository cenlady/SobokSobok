# 🍲 soboksobok Backend API Service

FastAPI 기반의 **soboksobok** 백엔드 서비스입니다.  
프로젝트 클론 후 로컬 개발 환경을 구축하고 실행하는 방법은 아래 가이드를 참고하세요.

---

## 🛠️ 개발 환경 요구사항
* **Python** (버전 3.11 이상)
* **Docker** 및 **Docker Compose** (PostgreSQL 데이터베이스 실행용)
* **Anaconda (Conda)** 또는 **virtualenv** (가상환경 관리용)

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 로컬 PostgreSQL 데이터베이스 실행 (Docker)
로컬 PC에 데이터베이스를 별도로 설치할 필요 없이 Docker Compose를 통해 띄울 수 있습니다.  
프로젝트 루트 디렉토리(`SobokSobok/`)에서 다음 명령어를 실행합니다.

```bash
# Docker 컨테이너를 백그라운드에서 실행
docker compose up -d
```
> [!NOTE]
> 데이터베이스가 정상적으로 켜졌는지 확인하려면 `docker ps` 명령어를 입력해 보세요.

---

### 2. 가상환경 설정 및 패키지 설치 (Anaconda 기준)
백엔드 디렉토리(`backend/`)로 이동한 후, 독립된 가상환경을 생성하고 패키지들을 설치합니다.

```bash
# 백엔드 디렉토리로 이동
cd backend

# Python 3.11 기반의 Conda 가상환경 생성 (최초 1회)
conda create -n soboksobok python=3.11 -y

# 가상환경 활성화
conda activate soboksobok

# 필요한 패키지 일괄 설치
pip install -r requirements.txt
```

---

### 3. 환경 변수 설정 (`.env`)
개발에 필요한 설정을 적용하기 위해 환경 변수 파일을 생성합니다.  
`backend/` 폴더 내의 `.env.example` 복사본을 만들어 `.env` 파일로 사용합니다.

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Mac / Linux
cp .env.example .env
```

* **`.env` 파일 기본 내용:**
  ```ini
  PROJECT_NAME="soboksobok"
  API_V1_STR="/api/v1"
  SECRET_KEY="super-secret-key-change-me-in-production"
  DATABASE_URL="postgresql://postgres:postgrespassword@localhost:5432/soboksobok"
  ```
  *(로컬 Docker PostgreSQL 정보와 자동으로 일치하게 설정되어 있습니다.)*

---

### 4. 백엔드 서버 실행
가상환경이 활성화된 상태에서 Uvicorn 개발 서버를 구동합니다.

```bash
# 핫 리로드(Hot-reload) 모드로 서버 실행
uvicorn app.main:app --reload
```
서버가 성공적으로 구동되면 터미널에 `INFO: Uvicorn running on http://127.0.0.1:8000` 문구가 출력됩니다.

---

## 📖 API 문서 확인 및 테스트
FastAPI에서 기본적으로 제공하는 대화형 API 문서를 통해 API를 직접 호출하고 테스트해 볼 수 있습니다.

* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📂 디렉토리 구조 설명
```text
backend/
├── app/
│   ├── api/           # API 엔드포인트 및 라우터 설정 폴더
│   │   ├── v1/        # v1 버전 API (auth.py, users.py)
│   │   └── api.py     # 모든 라우터를 병합하는 파일
│   ├── core/          # 데이터베이스 세션, 설정(Config) 등 핵심 공통 로직
│   ├── models/        # DB 테이블 엔티티 클래스 정의 폴더
│   ├── schemas/       # Pydantic 모델 (Request/Response DTO) 폴더
│   ├── crud/          # DB CRUD 처리 파일 폴더
│   └── main.py        # FastAPI 앱 생성 및 실행 엔트리포인트
├── requirements.txt   # 백엔드 의존성 패키지 관리 파일
├── .env               # 로컬 개발 환경 변수 (Git 무시됨)
└── .env.example       # 팀 협업용 환경 변수 샘플 파일
```
