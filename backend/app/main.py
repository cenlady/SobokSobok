from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.api.api import api_router
from app import models  # noqa: F401
from app.models.normalized_policy import ensure_normalized_policy_schema
from app.models.recommend import ensure_recommendation_vector_schema
from app.models.review import ensure_review_schema


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="soboksobok 백엔드 API 서비스",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS 설정
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 라우터 연결
app.include_router(api_router, prefix=settings.API_V1_STR)


from sqlalchemy import text


@app.on_event("startup")
def create_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        ensure_normalized_policy_schema(conn)
        ensure_recommendation_vector_schema(conn)
        ensure_review_schema(conn)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs"
    }
