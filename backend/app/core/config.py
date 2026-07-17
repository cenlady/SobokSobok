from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "soboksobok"
    SERVICE_NAME: str = "api"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    DATABASE_URL: str | None = None
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "soboksobok"
    DB_USER: str = "edu"
    DB_PASSWORD: str = ""
    SQL_ECHO: bool = False

    # 공급자 접속 설정. 모델과 임베딩 차원은 기능별 cloud/local 설정에서 관리한다.
    OPENAI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    GEMINI_API_KEY: str | None = None

    # 모델 호출 로그. 원문/응답 본문은 기본적으로 절대 기록하지 않는다.
    LLM_CALL_LOGGING_ENABLED: bool = True
    LLM_LOG_LEVEL: str = "INFO"
    LLM_LOG_CONTENT: bool = False
    LLM_LOG_PREVIEW_CHARS: int = 0
    LLM_REQUEST_TIMEOUT_SECONDS: float = 60.0
    LLM_EMBEDDING_TIMEOUT_SECONDS: float = 60.0

    # 챗봇 RAG 설정 (policy_documents → policy_chunks 청킹/임베딩)
    # OLLAMA_BASE_URL은 아래 공용 설정을 사용한다.
    CHAT_CLOUD_LLM_MODEL: str = "gpt-4o-mini"
    CHAT_LOCAL_LLM_MODEL: str = "exaone3.5"
    CHAT_ALLOW_EXTERNAL: bool = True
    CHAT_CLOUD_EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_CLOUD_EMBEDDING_DIMENSIONS: int = 1536
    CHAT_LOCAL_EMBEDDING_MODEL: str = "bge-m3"
    CHAT_LOCAL_EMBEDDING_DIMENSIONS: int = 1024
    CHAT_CHUNK_SIZE: int = 280
    CHAT_CHUNK_OVERLAP: int = 40
    CHAT_MIN_CHUNK_SIZE: int = 80
    CHAT_NEIGHBOR_CHUNK_WINDOW: int = 1
    CHAT_RETRIEVAL_LIMIT: int = 6
    EMBED_CHAT_CHUNKS_AFTER_NORMALIZE: bool = True
    CHAT_MAX_CONTEXT_CHARS: int = 4500
    CHAT_SYSTEM_PROMPT: str = (
        "너는 소상공인 정책 공고 안내 챗봇이다. "
        "반드시 제공된 검색 근거 안에서만 답하고, 근거가 부족하면 부족하다고 말한다. "
        "신청 대상, 신청 방법, 제출 서류, 접수 기간, 문의처를 사용자가 이해하기 쉽게 정리한다."
    )

    # 추천 설명 LLM + 추천 검색 임베딩.
    RECOMMEND_CLOUD_LLM_MODEL: str = "gpt-4o-mini"
    RECOMMEND_LOCAL_LLM_MODEL: str = "exaone3.5"
    RECOMMEND_ALLOW_EXTERNAL: bool = True
    RECOMMEND_CLOUD_EMBEDDING_MODEL: str = "text-embedding-3-small"
    RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS: int = 1536
    RECOMMEND_LOCAL_EMBEDDING_MODEL: str = "bge-m3"
    RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS: int = 1024

    # 정책 상세 요약. 사용자 cloud/local 선택에 맞춰 모델을 고른다.
    POLICY_SUMMARY_CLOUD_LLM_MODEL: str = "gpt-5.4-mini"
    POLICY_SUMMARY_LOCAL_LLM_MODEL: str = "exaone3.5"
    POLICY_SUMMARY_ALLOW_EXTERNAL: bool = True

    # 정책 정규화의 보조 추출. 공공 정책 원문을 구조화한다.
    NORMALIZATION_LLM_PROVIDER: str = "openai"
    NORMALIZATION_LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("NORMALIZATION_LLM_MODEL", "NORMALIZE_LLM_MODEL"),
    )
    NORMALIZATION_ALLOW_EXTERNAL: bool = True
    NORMALIZE_LLM_TIMEOUT_SECONDS: float = 30.0
    NORMALIZE_LLM_MAX_CONTEXT_CHARS: int = 800

    # 서류 검토는 로컬이 기본이지만, 사용자가 프로필에서 cloud/local을 선택할 수 있다.
    DOCUMENT_REVIEW_CLOUD_LLM_MODEL: str = "gpt-4o-mini"
    DOCUMENT_REVIEW_LOCAL_LLM_MODEL: str = "exaone3.5"
    DOCUMENT_REVIEW_CLOUD_EMBEDDING_MODEL: str = "text-embedding-3-small"
    DOCUMENT_REVIEW_CLOUD_EMBEDDING_DIMENSIONS: int = 1536
    DOCUMENT_REVIEW_LOCAL_EMBEDDING_MODEL: str = "bge-m3"
    DOCUMENT_REVIEW_LOCAL_EMBEDDING_DIMENSIONS: int = 1024
    REVIEW_VECTORS_ADVISORY_LOCK_ID: int = 2026070606
    # bge-m3 컨텍스트가 8192 토큰이라 긴 문서는 청킹 필요 (통째로 넣으면 뒷부분 소실)
    REVIEW_CHUNK_SIZE: int = 1000
    REVIEW_CHUNK_OVERLAP: int = 100
    # 임베딩 유사도는 "후보 필터"로만 쓰고, 최종 누락 판정은 LLM에 맡긴다.
    # 실측: 긴 쿼리에선 정답도 0.63까지 내려가고 오답도 0.66까지 올라와
    # 절대 임계값으로 정답/오답을 가를 수 없다(구간 겹침). 그래서 낮게 잡아
    # 후보만 거르고(0.55), 판정은 LLM(exaone3.5)이 원문 근거를 보고 내린다.
    REVIEW_CANDIDATE_THRESHOLD: float = 0.55
    REVIEW_UPLOAD_DIR: str = "./storage/review_uploads"
    REVIEW_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024  # 20MB
    REVIEW_LLM_TIMEOUT_SECONDS: int = 180

    # 서류 발급 가이드(prep_vectors)는 공유 지식이므로 두 임베딩을 미리 생성한다.
    # 실제 검색에서는 호출 기능의 cloud/local 선택에 맞는 컬럼만 사용한다.
    PREP_ALLOW_EXTERNAL: bool = True
    PREP_CLOUD_EMBEDDING_MODEL: str = "text-embedding-3-small"
    PREP_CLOUD_EMBEDDING_DIMENSIONS: int = 1536
    PREP_LOCAL_EMBEDDING_MODEL: str = "bge-m3"
    PREP_LOCAL_EMBEDDING_DIMENSIONS: int = 1024

    # 캘린더 일반 CRUD에는 적용되지 않고 AI 코칭에만 적용된다.
    CALENDAR_COACH_CLOUD_LLM_MODEL: str = "gpt-5.4-mini"
    CALENDAR_COACH_LOCAL_LLM_MODEL: str = "exaone3.5"
    CALENDAR_COACH_ALLOW_EXTERNAL: bool = True

    CRAWL_INTERVAL_SECONDS: int = 60 * 60 * 24
    NORMALIZE_AFTER_CRAWL: bool = True
    NORMALIZER_ADVISORY_LOCK_ID: int = 2026070604

    # 첨부파일 텍스트 추출 (kordoc 기반)
    EXTRACT_AFTER_NORMALIZE: bool = True
    EXTRACTOR_ADVISORY_LOCK_ID: int = 2026070605
    KORDOC_CMD: str = "kordoc"                 # 실행 커맨드 (경로 오버라이드용)
    KORDOC_TIMEOUT_SECONDS: int = 120          # 파일당 추출 타임아웃
    EXTRACT_MAX_CHARS: int = 1_000_000         # 행당 저장 상한 (초대형 문서 방어)
    EXTRACT_RETRY_FAILED: bool = False         # failed 상태 재시도 포함 여부
    EXTRACT_BATCH_LIMIT: int = 0               # 0=전체, N=한 실행당 N건
    SBIZ24_PAGE_SIZE: int = 100
    SBIZ24_REQUEST_DELAY_SECONDS: float = 1.0
    SEMAS_SEED_URL: str = "https://www.semas.or.kr/web/SUP01/SUP0122/SUP012201.kmdc"
    SEMAS_REQUEST_DELAY_SECONDS: float = 1.0
    GOV24_BASE_URL: str = "https://api.odcloud.kr/api"
    GOV24_SERVICE_KEY: str | None = None
    GOV24_SERVICE_LIST_USER_TYPE_LIKE: str | None = "소상공인"
    GOV24_PAGE_START: int = 1
    GOV24_PAGE_SIZE: int = 100
    GOV24_MAX_PAGES: int = 200
    GOV24_REQUEST_DELAY_SECONDS: float = 0.2
    GOV24_ADVISORY_LOCK_ID: int = 2026070603
    ATTACHMENT_DIR: str = "./storage/attachments"
    CRAWLER_ADVISORY_LOCK_ID: int = 2026070601
    SEMAS_CRAWLER_ADVISORY_LOCK_ID: int = 2026070602

    # Google OAuth 2.0 Settings
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    # 구글 콘솔에 등록된 값과 반드시 일치해야 한다. 콜백은 백엔드가 받고,
    # 토큰은 아래 FRONTEND_URL로 리다이렉트하며 넘긴다(콘솔 재등록 불필요).
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # 구글 콜백이 로그인 완료 후 사용자를 돌려보낼 프론트엔드 주소
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # React default port
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        # Docker, local run, CI 환경에서 같은 코드로 DB 접속 문자열을 만든다.
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if not self.DB_PASSWORD:
            raise ValueError("DB_PASSWORD must be set in .env or environment variables.")
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # 기존 코드가 읽는 이름만 유지한다. 환경설정은 cloud/local 변수가 단일 기준이다.
    @property
    def CHAT_COMPLETION_PROVIDER(self) -> str:
        return "openai"

    @property
    def CHAT_COMPLETION_MODEL(self) -> str:
        return self.CHAT_CLOUD_LLM_MODEL

    @property
    def REC_EMBEDDING_PROVIDER(self) -> str:
        return "openai"

    @property
    def REC_EMBEDDING_DIM(self) -> int:
        return self.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS

    @property
    def REC_OPENAI_MODEL(self) -> str:
        return self.RECOMMEND_CLOUD_EMBEDDING_MODEL

    @property
    def REC_OLLAMA_MODEL(self) -> str:
        return self.RECOMMEND_LOCAL_EMBEDDING_MODEL

    @property
    def REC_OLLAMA_BASE_URL(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def NORMALIZE_LLM_MODEL(self) -> str:
        return self.NORMALIZATION_LLM_MODEL

    @property
    def REVIEW_EMBEDDING_DIM(self) -> int:
        return self.DOCUMENT_REVIEW_LOCAL_EMBEDDING_DIMENSIONS

    @property
    def REVIEW_EMBEDDING_MODEL(self) -> str:
        return self.DOCUMENT_REVIEW_LOCAL_EMBEDDING_MODEL

    @property
    def REVIEW_LLM_MODEL(self) -> str:
        return self.DOCUMENT_REVIEW_LOCAL_LLM_MODEL


settings = Settings()
