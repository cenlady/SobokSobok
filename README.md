# SobokSobok

소상공인 지원사업 공고를 수집하고, 사용자에게 정책/혜택 정보를 제공하기 위한 서비스입니다.

현재 구성은 다음과 같습니다.

```text
frontend/  React + Vite
backend/   FastAPI + PostgreSQL + Docker crawler
```

## 현재 Docker 구성

`docker-compose.yml`에는 아래 서비스가 있습니다.

```text
api      FastAPI 백엔드 서버
crawler  소상공인24/SEMAS 주기 크롤러
db       PostgreSQL + pgvector 데이터베이스, 호스트 포트 5431
```

기본 실행은 Docker Compose 안의 `soboksobok_db` PostgreSQL + pgvector 컨테이너에 연결합니다.

컨테이너 내부에서 `api`와 `crawler`는 Compose 서비스 이름인 `db`로 PostgreSQL에 접속합니다.

```text
DB_HOST=db
DB_PORT=5432
DB_NAME=soboksobok
DB_USER=edu
DB_PASSWORD=<개인/팀 DB 비밀번호>
```

DBeaver처럼 호스트 PC에서 접속할 때는 compose 포트 매핑을 사용합니다.

```text
Host: localhost
Port: 5431
Database: soboksobok
User: edu
Password: 루트 .env의 DB_PASSWORD 값
```

기존 `edupgvector` 컨테이너는 더 이상 이 프로젝트의 기본 DB로 사용하지 않습니다. 포트 충돌을 피하기 위해 `soboksobok_db`는 호스트의 `5431` 포트로 노출합니다.

## 환경 변수

민감정보는 Git에 올리지 않는 루트 `.env`에서 관리합니다.

```powershell
cd C:\education\SobokSobok
Copy-Item .env.example .env
```

생성된 `.env`에서 `DB_PASSWORD`를 실제 값으로 바꿉니다.

```env
DB_PASSWORD=your-real-password
```

`.env`는 `.gitignore`에 포함되어 있으므로 커밋하지 않습니다. `.env.example`에는 실제 비밀번호를 적지 않습니다.

현재 Docker Compose 기준 주요 값은 아래와 같습니다.

```env
DB_HOST=db
DB_PORT=5432
DB_NAME=soboksobok
DB_USER=edu
DB_PASSWORD=<개인/팀 DB 비밀번호>
LOCAL_DB_PORT=5431
CRAWL_INTERVAL_SECONDS=86400
SEMAS_SEED_URL=https://www.semas.or.kr/web/SUP01/SUP0122/SUP012201.kmdc
SEMAS_REQUEST_DELAY_SECONDS=1.0
```

`DB_HOST=db`는 `api`, `crawler` 컨테이너가 같은 Compose 네트워크 안의 `db` 서비스로 접속한다는 뜻입니다. DBeaver처럼 호스트 PC에서 접속할 때는 `localhost:5431`을 사용합니다.

## 실행 방법

Docker Desktop을 먼저 켠 뒤 PowerShell에서 실행합니다.

```powershell
cd C:\education\SobokSobok
docker compose up -d --build
```

실행 상태 확인:

```powershell
docker compose ps
```

로그 확인:

```powershell
docker compose logs -f api
docker compose logs -f crawler
```

끄기:

```powershell
docker compose down
```

DB 볼륨까지 지우고 완전히 새 DB로 시작해야 할 때:

```powershell
docker compose down -v --remove-orphans
docker compose up -d --build
```

## API 확인

FastAPI 문서:

```text
http://localhost:8000/docs
```

정책 목록 API:

```text
http://localhost:8000/api/v1/policies/?limit=10
```

정책 상세 API:

```text
http://localhost:8000/api/v1/policies/{pbanc_sn}
```

예시:

```text
http://localhost:8000/api/v1/policies/791
```

SEMAS 지원사업 안내 페이지 API:

```text
http://localhost:8000/api/v1/policies/program-pages/?limit=10
```

## 크롤러 실행

`crawler` 서비스는 컨테이너가 실행되면 바로 1회 크롤링하고, 이후 하루에 한 번 소상공인24 공고와 SEMAS 지원사업 안내 페이지를 함께 반복 수집합니다.

주기 설정:

```text
CRAWL_INTERVAL_SECONDS=86400
```

크롤러만 1회 테스트:

```powershell
# 소상공인24 공고
docker compose run --rm crawler python -m app.jobs.crawl_sbiz24_once

# SEMAS 지원사업 안내 페이지
docker compose run --rm crawler python -m app.jobs.crawl_semas_once

# 소상공인24와 SEMAS를 모두 실행하는 주기 크롤러 모듈
docker compose run --rm crawler python -m app.jobs.crawl_policy_sources_loop
```

크롤러 주기 실행 시작:

```powershell
docker compose up -d crawler
```

크롤러 로그:

```powershell
docker compose logs -f crawler
```

## 수집 대상

소상공인24 통합공고 목록은 아래 조건을 사용합니다.

```text
지원대상: 소상공인
분류: 공단지원사업
신청가능: Y
```

SEMAS는 `SEMAS_SEED_URL` 페이지에서 `/web/SUP01/...kmdc` 지원사업 링크를 모아 각 안내 페이지의 본문을 저장합니다.

수집 데이터:

```text
policy_announcements  공고 목록/상세 본문/원본 JSON/content_hash
policy_attachments    첨부파일 메타데이터/저장 경로/file_hash
policy_program_pages  SEMAS 지원사업 안내 페이지 본문/섹션/content_hash
```

첨부파일은 DB에 bytes로 저장하지 않고, 디스크에 저장한 뒤 DB에는 경로와 해시만 저장합니다.

```text
DB saved_path -> /app/storage/attachments/{pbanc_sn}/{file_name}
backend/storage/attachments/{pbanc_sn}/
```

`backend/storage/`는 Git에 올리지 않습니다.

## DB 확인

DBeaver에서 compose DB를 보려면 아래 설정으로 연결합니다.

```text
Host: localhost
Port: 5431
Database: soboksobok
Username: edu
Password: 루트 .env의 DB_PASSWORD 값
```

테이블 위치:

```text
soboksobok
-> Schemas
-> public
-> Tables
-> policy_announcements
-> policy_attachments
-> policy_program_pages
```

확인용 SQL:

```sql
SELECT COUNT(*) FROM policy_announcements;
SELECT COUNT(*) FROM policy_attachments;
SELECT COUNT(*) FROM policy_program_pages;

SELECT pbanc_sn, title, apply_end, status, last_seen_at
FROM policy_announcements
ORDER BY last_seen_at DESC
LIMIT 10;
```

```sql
SELECT id, category, program_name, source_url, last_seen_at
FROM policy_program_pages
ORDER BY last_seen_at DESC
LIMIT 10;
```
기존 `edupgvector` 컨테이너가 켜져 있어도 이 프로젝트는 `soboksobok_db`를 사용합니다. 기존 DB 컨테이너가 필요 없다면 Docker Desktop에서 별도로 중지해도 됩니다.

DBeaver에서 테이블이 보이지 않으면 먼저 컨테이너 상태를 확인합니다.

```powershell
docker compose ps
```

`soboksobok_db`의 포트가 아래처럼 보여야 합니다.

```text
0.0.0.0:5431->5432/tcp
```

테이블은 FastAPI 서버 시작 시 SQLAlchemy `create_all()`로 생성됩니다. 데이터가 비어 있으면 크롤러 1회 실행 명령으로 수집을 시작할 수 있습니다.

`soboksobok_db`는 pgvector 지원 이미지를 사용합니다. 다만 임베딩/벡터 검색용 테이블과 `vector` extension 생성은 아직 크롤러 저장 로직과 별도 작업입니다.
