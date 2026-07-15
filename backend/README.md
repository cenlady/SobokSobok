# SobokSobok Backend

FastAPI 기반 백엔드입니다. 현재 백엔드는 정책 조회 API, 소상공인24/Gov24/SEMAS 크롤러,
정책 정규화와 챗/추천/서류 요건/발급 가이드 이중 임베딩 파이프라인을 포함합니다.

## 주요 구성

```text
FastAPI                API 서버
SQLAlchemy             PostgreSQL 연결/모델
PostgreSQL             정책 공고/첨부파일 메타데이터 저장
Docker crawler service 소상공인24/Gov24/SEMAS 주기 크롤링 후 정규화
```

## DB 연결 방식

기본 Docker 실행은 Compose 안의 `soboksobok_db` PostgreSQL + pgvector 컨테이너를 사용합니다. 호스트 PC에는 `5431` 포트로 노출됩니다.

Docker 컨테이너 내부에서는 Compose 서비스 이름인 `db`로 접속합니다.

```env
DB_HOST="db"
DB_PORT="5432"
DB_NAME="soboksobok"
DB_USER="edu"
DB_PASSWORD="<개인/팀 DB 비밀번호>"
```

로컬 Python 실행에서는 호스트 포트로 노출된 compose DB에 접속합니다.

```env
DB_HOST="localhost"
DB_PORT="5431"
DB_NAME="soboksobok"
DB_USER="edu"
DB_PASSWORD="<개인/팀 DB 비밀번호>"
```

`DATABASE_URL`을 직접 설정하면 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`보다 우선합니다.

```env
DATABASE_URL="postgresql://edu:<password>@localhost:5431/soboksobok"
```

## 민감정보 관리

실제 비밀번호와 시크릿은 Git에 커밋하지 않습니다.

Docker Compose 실행용 환경변수는 프로젝트 루트의 `.env`에서 관리합니다.

```powershell
cd C:\education\SobokSobok
Copy-Item .env.example .env
```

로컬 Python 실행용 환경변수는 `backend/.env`에서 관리할 수 있습니다.

```powershell
cd C:\education\SobokSobok\backend
Copy-Item .env.example .env
```

Docker Compose로 실행할 때는 프로젝트 루트의 `.env`가 기준입니다. `backend/.env`는 `uvicorn app.main:app --reload`처럼 백엔드를 로컬 Python으로 직접 실행할 때 사용합니다.

### 기능별 AI 설정과 사용자 선택

모든 모델 생성은 `app/core/model_provider.py`의 중앙 factory를 통과합니다. `.env`의
기능별 provider는 `openai`, `ollama`, `gemini` 중에서 고를 수 있고, 모델명과 임베딩
차원을 함께 설정해야 합니다.

사용자 프로필에는 챗봇·추천·정책 요약·캘린더 코치·서류검토의 `cloud`/`local`
선택을 각각 저장합니다. 일반 기능 기본값은 `cloud`, 서류검토 기본값은 `local`입니다.
정책 정규화처럼 사용자와 무관한 배치는 기능별 `.env` provider를 그대로 사용합니다.
서류 파일 파싱은 선택과 관계없이 로컬에서 처리하며, 서류검토를 `cloud`로 선택하면
파싱된 내용과 유형명이 OpenAI API로 전달됩니다.

챗봇 `policy_chunks`, 추천 `rec_vectors`, 서류 요건 `review_vectors`, 발급 가이드
`prep_vectors`는 사용자 전환을 위해 다음 벡터를 모두 가집니다.

- `embedding_openai`: `text-embedding-3-small`, 기본 1536차원
- `embedding_ollama`: `bge-m3`, 기본 1024차원

두 벡터는 서로 다른 pgvector 컬럼이므로 차원이 섞이지 않습니다. 크롤러는 시작 직후와
매 수집 주기마다 원문·모델·양쪽 벡터를 비교해 신규·변경·누락분만 갱신합니다. 같은 데이터는
OpenAI/Ollama에 다시 보내지 않습니다. 수동 증분 실행:

```powershell
docker compose exec api python -m app.jobs.embed_policy_chunks_once
docker compose exec api python -m app.jobs.build_rec_vectors_once
docker compose exec api python -m app.jobs.build_review_vectors_once
docker compose exec api python -m app.jobs.build_prep_vectors_once
```

전체 재생성은 채팅의 `--force` 또는 검토의 `--rebuild` 옵션을 명시한 경우에만 수행합니다.

`prep_vectors`는 `build_prep_vectors_once`만 실제 적재를 담당합니다. 이전 명령인
`ingest_prep_guide`도 호환을 위해 같은 작업으로 위임하며 정책 일정 단락으로 테이블을
덮어쓰지 않습니다. 캘린더 코치는 프로필의 cloud/local 설정과 같은 Prep 벡터 컬럼을
검색한 뒤 같은 모드의 LLM으로 일정을 생성합니다.

모델 호출 로그에는 feature/provider/model/stage/source, 입력·출력 길이, 결과 수, 차원,
지연시간, 상태와 오류 타입만 한 줄로 남습니다. 프롬프트·응답 원문·벡터·키·파일명은
출력하지 않습니다.

## Docker 실행

프로젝트 루트에서 실행합니다.

```powershell
cd C:\education\SobokSobok
docker compose up -d --build
```

상태 확인:

```powershell
docker compose ps
```

API 로그:

```powershell
docker compose logs -f api
```

크롤러 로그:

```powershell
docker compose logs -f crawler
```

종료:

```powershell
docker compose down
```

DB 볼륨까지 지우고 새 데이터베이스로 다시 시작:

```powershell
docker compose down -v --remove-orphans
docker compose up -d --build
```

## 로컬 Python 실행

백엔드 디렉토리에서 실행합니다.

```powershell
cd C:\education\SobokSobok\backend
Copy-Item .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API 문서:

```text
http://localhost:8000/docs
```

## 크롤러와 정규화 파이프라인

크롤러 컨테이너는 같은 주기 안에서 소상공인24 공고, SEMAS 지원사업 안내 페이지, Gov24 OpenAPI 데이터를 순차적으로 수집합니다. 이후 `1차 정규화(첨부 링크 동기화) → 첨부 본문 추출 → 추출 성공 시 2차 정규화 → 임베딩` 순서로 실행합니다. 따라서 새 첨부의 구비서류도 다음 수집 주기를 기다리지 않고 같은 주기에 반영됩니다.

```text
CRAWL_INTERVAL_SECONDS=86400
NORMALIZE_AFTER_CRAWL=true
```

즉 컨테이너가 켜지면 바로 1회 실행하고, 이후 하루에 한 번 반복 실행합니다.

주기 실행 entrypoint:

```text
app.jobs.crawl_policy_sources_loop
```

1회 실행 entrypoint:

```text
app.jobs.crawl_sbiz24_once
app.jobs.crawl_semas_once
app.jobs.crawl_gov24_once
app.jobs.normalize_policies_once
```

소상공인24 1회 테스트:

```powershell
docker compose run --rm crawler python -m app.jobs.crawl_sbiz24_once
```

SEMAS 1회 테스트:

```powershell
docker compose run --rm crawler python -m app.jobs.crawl_semas_once
```

Gov24 1회 테스트:

```powershell
docker compose run --rm crawler python -m app.jobs.crawl_gov24_once
```

정규화 1회 테스트:

```powershell
docker compose run --rm crawler python -m app.jobs.normalize_policies_once
```

실제 공고 50건 골드셋 기반 정규화 품질 측정:

```powershell
docker compose run --rm crawler python -m app.jobs.evaluate_normalization_quality
```

출력에는 지역·업종·구비서류의 precision/recall/F1, 조건 모드 정확도와 오답 목록이 포함됩니다. 골드셋은 `tests/fixtures/normalization_gold_cases.json`에 원천 ID와 검토 근거 문구를 함께 보관하며, 전체 테스트에서 최소 품질 기준을 검사합니다.

### 소상공인24 수집 조건

```text
지원대상: 소상공인
분류: 공단지원사업
신청가능: Y
```

### SEMAS 수집 방식

SEMAS는 공고 API가 아니라 공단 홈페이지의 지원사업 안내 HTML 페이지를 수집합니다.

기본 seed URL:

```text
https://www.semas.or.kr/web/SUP01/SUP0122/SUP012201.kmdc
```

seed 페이지에서 `/web/SUP01/...kmdc` 형태의 지원사업 링크를 모아 각 페이지의 본문(`div.contents`)을 저장합니다.

## 중복 방지

공고는 `pbanc_sn`을 기준으로 중복 저장을 막습니다.

```text
policy_announcements.pbanc_sn
```

첨부파일은 `file_id`를 기준으로 중복 저장을 막습니다.

```text
policy_attachments.file_id
```

본문 변경 여부는 `content_hash`로 추적합니다. 크롤러가 같은 공고를 다시 만나면 `pbanc_sn` 기준으로 기존 row를 갱신하고, 같은 첨부파일은 `file_id` 기준으로 재다운로드하지 않습니다.

SEMAS 지원사업 안내 페이지는 `source_url`을 기준으로 중복 저장을 막습니다.

```text
policy_program_pages.source_url
```

Gov24는 `service_id`를 기준으로 목록/상세/지원조건 중복 저장을 막습니다.

```text
gov24_service_lists.service_id
gov24_service_details.service_id
gov24_support_conditions.service_id
```

정규화 공고는 원천별 고유 키인 `source + source_pk` 조합으로 중복 저장을 막습니다.

```text
normalized_policies(source, source_pk)
```

정규화 문서는 원천 내용이 바뀌었거나 아직 문서가 없을 때 다시 구성합니다. 크롤러 주기에는
`policy_chunks`, `rec_vectors`, `review_vectors`, `prep_vectors`가 모두 점검되며 신규·변경·누락분만
임베딩합니다. 업로드한 사용자 서류 원문은 이 공유 벡터 작업에 포함되지 않습니다.

### 정규화 기준

정규화는 임베딩 직전의 공통 재료를 만드는 단계입니다. raw 테이블을 직접 임베딩하지 않고, 각 도메인 job은 `normalized_policies`, `policy_documents`, `attachment_files`를 읽습니다.

```text
Gov24
- 목록/상세/지원조건 테이블을 service_id로 조인
- 지원조건 코드(JA*)를 eligibility.support_condition_labels, industry_tags, business_status_tags로 매핑
- 나이/소득/대상특성 코드는 eligibility.age, income_ranges, target_traits에 보관

Sbiz24
- 공고 상세 content_text에서 지원대상/지원내용/신청방법/문의처/신청서류 표제를 rule 기반 분리
- target/category/apply 기간과 첨부파일 연결 정보를 함께 보관

SEMAS
- sections_json을 표준 document_type으로 매핑
- breadcrumbs/category/content_text로 업종, 대상 상태, 신청방법, 연락처를 보강
```

`eligibility` JSON에는 아래 구조화 공통 필드를 포함합니다.

```text
region
- region_scope: national/local/unknown
- condition_mode: restricted/unrestricted/unknown
- sido, sigungu
- matched_sidos: 권역 표현을 여러 시도로 푼 리스트
- confidence, extraction_method, source_ref, evidence
business_status_tags
industry_tags
industry_condition
- mode: restricted/unrestricted/unknown
- include_tags, exclude_tags
- confidence, extraction_method, evidence
employee_limit
- value, operator, unit, source_text
sales_limit
- amount_krw, operator, source_text
business_age_limit
- value, operator, unit, source_text ("~년이 경과하지 않은 자" 등의 엣지 케이스 포함)
money_conditions
application_methods
contacts
```

`policy_documents.document_type`은 다음 RAG 분할 기준 값을 사용합니다.

```text
summary         (요약 / 사업목적)
support_content (지원 내용 및 혜택 규모)
eligibility     (지원 대상 및 조건)
application     (신청 방법 및 신청 접수처)
deadline        (신청 기간 및 제출 마감일)
requirements    (필수 구비 서류 목록)
contact         (문의처 연락처 및 전화번호)
procedure       (추진 절차 및 단계)
reference       (관련 법령 및 참조)
body            (공고문 본문 전체 백업)
section         (기타 일반 세부 섹션)
```

`required_documents`는 확실한 구비서류만 보수적으로 채웁니다. 첨부 전문을 훑지 않고 `제출서류`, `구비서류`, `신청서류`, `준비서류` 같은 명시적 제목 아래 구간만 읽으며, HTML 태그·발급 안내·일반 문장·`자료/서류` 같은 포괄어는 문서명에서 제외합니다. 규칙으로 확정하지 못했지만 문서형 명사로 끝나는 짧은 후보만 `NORMALIZATION_LLM_PROVIDER`/`NORMALIZATION_LLM_MODEL`이 `document / not_document`로 판정합니다. 기본값은 OpenAI `gpt-4o-mini`이며 Ollama 등으로 변경할 수 있습니다. 후보가 해당 서류 구간에 실제 존재하는지는 코드가 재확인하고, 모델은 문서명을 생성하지 않으며 처음 추출한 원문 후보만 낮은 신뢰도의 보완 결과로 반영합니다. 결과는 원문·문맥 해시와 provider·모델·프롬프트 버전별로 캐시합니다. 첨부 parser/OCR가 새 본문을 만들면 같은 수집 주기의 2차 정규화에서 보강됩니다.

## 저장 테이블

데이터는 세 계층으로 나눕니다.

```text
1. raw 원천 수집 테이블
2. normalized 공유 테이블
3. domain vector 테이블
```

```text
policy_announcements
- pbanc_sn
- title
- target
- category
- organization
- apply_start
- apply_end
- status
- detail_url
- content_html
- content_text
- raw_list_json
- raw_detail_json
- content_hash
- first_seen_at
- last_seen_at
- is_active

policy_attachments
- file_id
- pbanc_sn
- file_name
- file_size
- saved_path
- file_hash
- raw_file_json
- created_at
- downloaded_at
```

```text
policy_program_pages
- id
- source
- source_url
- category
- program_name
- content_html
- content_text
- sections_json
- raw_breadcrumbs_json
- content_hash
- first_seen_at
- last_seen_at
- is_active
```

```text
gov24_service_lists
gov24_service_details
gov24_support_conditions
```

정규화 공유 테이블 (최신 추천 사전필터 고속 컬럼 포함):

```text
normalized_policies
- id (UUID PK)
- source
- source_pk
- canonical_key
- duplicate_group_key
- title
- summary
- body
- organization
- support_type
- target_text
- support_content
- region_scope
- status
- apply_start
- apply_end
- apply_url
- matched_sidos             (JSON: 권역 포함 적용 가능 시도 목록 GIN 인덱스)
- region_confidence         (Double: 지역 추출 신뢰도 점수)
- application_methods       (JSON: 신청 방법 태그 리스트 GIN 인덱스)
- contact_points            (JSON: 문의처 전화번호 목록)
- employee_limit_value      (Integer: 상시근로자수 제한 제한치)
- employee_limit_operator   (String: 상시근로자수 대소비교 기호)
- sales_limit_amount_krw    (BigInt: 연 매출액 제한값 원 단위)
- sales_limit_operator      (String: 매출액 대소비교 기호)
- business_age_limit_value  (Integer: 창업 연차 조건 제한치)
- business_age_limit_operator (String: 창업 연차 대소비교 기호)
- required_document_count   (Integer: 필수 제출서류 개수)
- has_required_documents    (Boolean: 필수 제출서류 정규화 유무)
- industry_tags             (JSON: 대상 업종 태그 GIN 인덱스)
- business_status_tags      (JSON: 대상 기업상태 태그 GIN 인덱스)
- eligibility               (JSON: 상세 자격 조건)
- required_documents        (JSON: 상세 구비 서류 객체 목록)
- source_content_hash
- normalized_hash
- is_active
```

attachment_files
- file_hash
- storage_path
- original_file_name
- content_type
- file_size
- extracted_text
- extraction_status

policy_attachment_links
- policy_id
- attachment_file_id
- source_file_id
- original_file_name

policy_documents
- policy_id
- document_type
- source_ref
- title
- text
- text_hash
```

도메인별 벡터 테이블 및 사용자 프로필:

```text
rec_vectors (추천 서비스 소유)
- policy_id (UUID FK)
- embedding_openai (VECTOR(1536))
- embedding_ollama (VECTOR(1024))
- embedding_openai_model / embedding_ollama_model

policy_chunks (챗봇 RAG 소유)
- policy_id (UUID FK)
- document_id (UUID FK)
- chunk_index (INTEGER)
- chunk_text (TEXT)
- chunk_hash (VARCHAR)
- metadata (JSON)
- embedding_status (VARCHAR)
- embedding_model (TEXT)
- embedding_openai (VECTOR(1536))
- embedding_ollama (VECTOR(1024))
- embedding_openai_model / embedding_ollama_model

review_vectors (서류 검토 소유)
- policy_id (UUID FK)
- document_name (VARCHAR)
- source_text (TEXT)
- embedding_openai (VECTOR(1536))
- embedding_ollama (VECTOR(1024))
- embedding_openai_model / embedding_ollama_model

prep_vectors (일정/준비 가이드 소유)
- document_name (VARCHAR)
- guide_text (TEXT)
- embedding_openai (VECTOR(1536))
- embedding_ollama (VECTOR(1024))
- embedding_openai_model / embedding_ollama_model

users (인증 공통)
- email (VARCHAR)
- hashed_password (VARCHAR)
- is_active (BOOLEAN)

user_profiles (추천 필터 공통)
- user_id (INTEGER FK)
- industry (JSON)
- region (VARCHAR)
- sales (INTEGER)
- employees (INTEGER)
- available_time_preference (JSON)
```

벡터 테이블은 공유 정규화 데이터를 읽어서 각 도메인이 채우는 영역입니다. 네 테이블 모두
크롤러 주기에 자동 점검되고 원문·모델·벡터 상태가 달라진 항목만 갱신합니다. 사용자가
업로드한 서류 원문은 `review_vectors`에 저장하거나 공유 임베딩하지 않습니다.

첨부파일 실제 저장 위치:

```text
backend/storage/attachments/{pbanc_sn}/
```

첨부파일 bytes는 DB에 직접 넣지 않습니다. DB에는 `saved_path`, `file_hash`, 파일 메타데이터만 저장합니다.

## 정책 API

목록:

```text
GET /api/v1/policies/
```

상세:

```text
GET /api/v1/policies/{pbanc_sn}
```

SEMAS 지원사업 안내 페이지 목록:

```text

첨부파일 실제 저장 위치:

```text
backend/storage/attachments/{pbanc_sn}/
```

첨부파일 bytes는 DB에 직접 넣지 않습니다. DB에는 `saved_path`, `file_hash`, 파일 메타데이터만 저장합니다.

## 정책 API

목록:

```text
GET /api/v1/policies/
```

상세:

```text
GET /api/v1/policies/{pbanc_sn}
```

SEMAS 지원사업 안내 페이지 목록:

```text
GET /api/v1/policies/program-pages/
```

상세는 `GET /api/v1/policies/program-pages/{page_id}`로 조회합니다.

브라우저 예시:

```text
http://localhost:8000/api/v1/policies/?limit=10
http://localhost:8000/api/v1/policies/791
http://localhost:8000/api/v1/policies/program-pages/?limit=10
```

## 파일 구조

```text
backend/
├── Dockerfile
├── requirements.txt
├── .env.example
└── app/
    ├── api/
    │   ├── api.py
    │   └── v1/
    │       ├── auth.py
    │       ├── calendar.py
    │       ├── chat.py
    │       ├── policies.py
    │       ├── recommend.py
    │       ├── review.py
    │       └── users.py
    ├── core/
    │   ├── config.py
    │   ├── database.py
    │   └── rag_utils.py
    ├── crawlers/
    │   ├── gov24_client.py
    │   ├── sbiz24_client.py
    │   └── semas_client.py
    ├── crud/
    │   └── policy.py
    ├── jobs/
    │   ├── crawl_gov24_once.py
    │   ├── crawl_policy_sources_loop.py
    │   ├── crawl_sbiz24_once.py
    │   ├── crawl_semas_once.py
    │   ├── evaluate_normalization_quality.py
    │   └── normalize_policies_once.py
    ├── models/
    │   ├── chat.py
    │   ├── gov24.py
    │   ├── normalized_policy.py
    │   ├── policy.py
    │   ├── prep.py
    │   ├── recommend.py
    │   ├── review.py
    │   └── user.py
    ├── schemas/
    │   └── policy.py
    ├── services/
    │   ├── gov24_ingest.py
    │   ├── normalize_policies.py       # 정규화 잡 진입점·락 관리
    │   ├── normalization/
    │   │   ├── common.py               # 공통 텍스트·해시 유틸
    │   │   ├── documents.py            # 섹션 유형·구비서류 추출
    │   │   ├── field_extractors.py      # 연락처·신청방법·기본 수치 추출
    │   │   ├── limit_rules.py           # 직원수·매출·업력 규칙 검증
    │   │   ├── llm_documents.py         # 기능별 LLM 구비서류 후보 판정·검증·캐시
    │   │   ├── llm_limits.py            # 기능별 LLM 보완 추출·검증·캐시
    │   │   ├── metadata.py              # 공통 메타데이터·날짜·필터 컬럼
    │   │   ├── persistence.py           # 정책·문서·첨부파일 DB 반영
    │   │   ├── regions.py               # 시도·시군구·권역 정규화
    │   │   ├── source_documents.py      # 출처별 문서·섹션 구성
    │   │   └── sources.py               # Sbiz24·SEMAS·Gov24 변환 어댑터
    │   ├── policy_ingest.py
    │   └── semas_ingest.py
    └── main.py
```

## DBeaver에서 확인

compose DB는 아래 설정으로 확인합니다.

```text
Host: localhost
Port: 5431
Database: soboksobok
Username: edu
Password: .env의 DB_PASSWORD 값
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

확인 SQL:

```sql
SELECT COUNT(*) FROM policy_announcements;
SELECT COUNT(*) FROM policy_attachments;
SELECT COUNT(*) FROM policy_program_pages;
```

`localhost:5431`은 compose의 `soboksobok_db` 컨테이너 내부 5432 포트에 매핑됩니다.

연결이 실패하면 먼저 Docker 상태를 확인합니다.

```powershell
cd C:\education\SobokSobok
docker compose ps
```

`soboksobok_db`가 실행 중이고 `0.0.0.0:5431->5432/tcp` 포트 매핑이 보여야 합니다. 테이블은 FastAPI 서버 시작 시 `Base.metadata.create_all(bind=engine)`로 생성됩니다.

수집 데이터가 비어 있으면 필요한 출처별로 크롤러를 한 번 실행합니다.

```powershell
docker compose run --rm crawler python -m app.jobs.crawl_sbiz24_once
docker compose run --rm crawler python -m app.jobs.crawl_semas_once
docker compose run --rm crawler python -m app.jobs.crawl_policy_sources_loop
```

현재 DB 이미지는 pgvector를 지원하고, `CREATE EXTENSION vector` 및 테이블 생성은 FastAPI
startup에서 처리합니다. Compose 기준 실행 흐름은 `api 테이블/벡터 스키마 생성 -> crawler raw
수집 -> normalizer 정규화 -> 네 벡터 테이블의 변경분 이중 임베딩 갱신`입니다.
