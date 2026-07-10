from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "soboksobok"
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

    # RAG 임베딩 벡터 차원. 사용하는 임베딩 모델에 맞춰 조정한다.
    # 예: OpenAI text-embedding-3-small = 1536, bge-m3 = 1024
    EMBEDDING_DIM: int = 1536
    REC_EMBEDDING_DIM: int = 1024
    REC_EMBEDDING_PROVIDER: str = "ollama"
    REC_OLLAMA_MODEL: str = "bge-m3:latest"
    REC_OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    REC_OPENAI_MODEL: str = "text-embedding-3-small"
    GEMINI_API_KEY: str | None = None
    GEMINI_TEXT_MODEL: str = "gemini-2.5-flash"

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


settings = Settings()
