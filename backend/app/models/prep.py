# -*- coding: utf-8 -*-
# 파일 역할: [서류 검토 영역] 서류 발급 가이드(prep_vectors) ORM 모델

import uuid

from sqlalchemy import Column, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base


class PrepVector(Base):
    """
    [서류 검토 영역] 서류 발급 가이드 지식베이스

    - 역할: 서류명 → 발급처·발급 방법·소요 기간·수수료·팁.
    - 소상공인이 지원금을 못 받는 이유는 '무슨 서류가 필요한지 몰라서'만이 아니다.
      이름을 알아도 '어디서 어떻게 떼는지' 몰라서 못 낸다. 목록만 던지는 건 절반이다.
    - 임베딩: OpenAI와 Ollama 벡터를 모두 저장하고 호출 기능의 AI 설정에 맞춰 검색한다.
    """

    __tablename__ = "prep_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_name = Column(String(255), nullable=False, index=True, comment="가이드 대상 서류명 (정규화됨)")
    guide_text = Column(Text, nullable=True, comment="발급처·방법·소요기간·수수료·팁")

    embedding_openai = Column(
        Vector(settings.PREP_CLOUD_EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="[pgvector] 클라우드 AI용 OpenAI 발급 가이드 벡터",
    )
    embedding_ollama = Column(
        Vector(settings.PREP_LOCAL_EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="[pgvector] 로컬 AI용 Ollama 발급 가이드 벡터",
    )
    embedding_openai_model = Column(String(100), nullable=True)
    embedding_ollama_model = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


PREP_SCHEMA_SQL = [
    f"ALTER TABLE prep_vectors ADD COLUMN IF NOT EXISTS embedding_openai vector({settings.PREP_CLOUD_EMBEDDING_DIMENSIONS})",
    f"ALTER TABLE prep_vectors ADD COLUMN IF NOT EXISTS embedding_ollama vector({settings.PREP_LOCAL_EMBEDDING_DIMENSIONS})",
    "ALTER TABLE prep_vectors ADD COLUMN IF NOT EXISTS embedding_openai_model VARCHAR(100)",
    "ALTER TABLE prep_vectors ADD COLUMN IF NOT EXISTS embedding_ollama_model VARCHAR(100)",
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'prep_vectors'::regclass
              AND (
                    (attname = 'embedding_openai' AND atttypmod <> {settings.PREP_CLOUD_EMBEDDING_DIMENSIONS})
                 OR (attname = 'embedding_ollama' AND atttypmod <> {settings.PREP_LOCAL_EMBEDDING_DIMENSIONS})
              )
        ) THEN
            DELETE FROM prep_vectors;
            ALTER TABLE prep_vectors
                ALTER COLUMN embedding_openai TYPE vector({settings.PREP_CLOUD_EMBEDDING_DIMENSIONS});
            ALTER TABLE prep_vectors
                ALTER COLUMN embedding_ollama TYPE vector({settings.PREP_LOCAL_EMBEDDING_DIMENSIONS});
        END IF;
    END $$;
    """,
    "ALTER TABLE prep_vectors DROP COLUMN IF EXISTS embedding",
]


def ensure_prep_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in PREP_SCHEMA_SQL:
        bind.execute(text(statement))
