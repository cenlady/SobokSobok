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
    # 예: OpenAI text-embedding-3-small = 1536, Gemini text-embedding-004 = 768
    #
    # 공유 계약 #1: "공유하는 건 텍스트, 각자 소유하는 건 벡터" — 도메인마다 다른
    # 임베딩 모델을 쓸 수 있어야 하므로 벡터 테이블별로 차원을 분리해 관리한다.
    # 아래 값을 지정하지 않은 테이블은 EMBEDDING_DIM을 따른다.
    EMBEDDING_DIM: int = 1536

    # [서류 검토] Ollama bge-m3 = 1024차원 (실측 확인)
    REVIEW_EMBEDDING_DIM: int = 1024

    # 서류 검토 (이슈 #6) — 로컬 Ollama 사용
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"  # 컨테이너 → 호스트 Ollama
    REVIEW_EMBEDDING_MODEL: str = "bge-m3"        # 임베딩 (1024차원, 다국어)
    REVIEW_LLM_MODEL: str = "exaone3.5"           # 진단용 LLM (한국어 특화)
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
