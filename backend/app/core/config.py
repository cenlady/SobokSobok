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
    
    CRAWL_INTERVAL_SECONDS: int = 60 * 60 * 24
    SBIZ24_PAGE_SIZE: int = 100
    SBIZ24_REQUEST_DELAY_SECONDS: float = 1.0
    SEMAS_SEED_URL: str = "https://www.semas.or.kr/web/SUP01/SUP0122/SUP012201.kmdc"
    SEMAS_REQUEST_DELAY_SECONDS: float = 1.0
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
