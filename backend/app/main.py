import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import Base, engine
from app.core.model_errors import ModelServiceError
from app.core.model_provider import validate_model_settings
from app.api.api import api_router
from app import models  # noqa: F401
from app.models.normalized_policy import ensure_normalized_policy_schema
from app.models.chat import ensure_policy_chunk_schema
from app.models.recommend import ensure_recommendation_vector_schema
from app.models.prep import ensure_prep_schema
from app.models.review import ensure_review_legacy_cleanup, ensure_review_schema
from app.models.user import ensure_user_legacy_cleanup, ensure_user_schema


model_error_logger = logging.getLogger("app.model_errors")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="soboksobok 백엔드 API 서비스",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)


@app.exception_handler(ModelServiceError)
async def model_service_error_handler(request: Request, exc: ModelServiceError) -> JSONResponse:
    """모델 SDK의 원문 오류·키·요청 내용을 노출하지 않고 일관된 상태로 응답한다."""
    model_error_logger.warning(
        "model_error path=%s feature=%s task=%s provider=%s model=%s "
        "status_code=%s error_code=%s",
        request.url.path,
        exc.feature or "-",
        exc.task or "-",
        exc.provider or "-",
        exc.model or "-",
        exc.status_code,
        exc.code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.public_message, "error_code": exc.code},
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
    # DB 작업 전에 provider/model/dimension/개인정보 게이트 조합을 검증한다.
    validate_model_settings()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # 구 스키마 정리는 create_all()보다 먼저. 호환되지 않는 옛 테이블을 버려야
        # create_all()이 새 정의로 다시 만들 수 있다. (버린 뒤 만들지 않으면 테이블이 사라진다)
        ensure_user_legacy_cleanup(conn)
        ensure_review_legacy_cleanup(conn)

    Base.metadata.create_all(bind=engine)

    # 이하는 이미 존재하는 테이블에 컬럼/인덱스/제약을 덧붙이는 패치들이라 create_all() 이후.
    with engine.begin() as conn:
        ensure_user_schema(conn)
        ensure_normalized_policy_schema(conn)
        ensure_policy_chunk_schema(conn)
        ensure_recommendation_vector_schema(conn)
        ensure_review_schema(conn)
        ensure_prep_schema(conn)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs"
    }
