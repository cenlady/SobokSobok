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
    - 임베딩: bge-m3 (1024차원). 서류명이 정확히 일치하지 않아도 찾을 수 있게 한다.
    """

    __tablename__ = "prep_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_name = Column(String(255), nullable=False, index=True, comment="가이드 대상 서류명 (정규화됨)")
    guide_text = Column(Text, nullable=True, comment="발급처·방법·소요기간·수수료·팁")

    embedding = Column(
        Vector(settings.EMBEDDING_DIM),
        nullable=False,
        comment="[pgvector] bge-m3 임베딩 (차원은 settings.EMBEDDING_DIM)",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# 이 테이블은 임베딩 모델이 bge-m3(1024)로 통일되기 '전'에 만들어졌다. 그때 차원이
# 1536(OpenAI)이었고, 모델 정의만 1024로 바뀌었을 뿐 DB 컬럼은 그대로 굳어 있었다.
# create_all()은 기존 테이블의 컬럼 타입을 바꿔주지 않는다.
#
# 그래서 적재를 시도하면 이렇게 죽는다:
#     psycopg2.errors.DataException: expected 1536 dimensions, not 1024
#
# 차원이 이미 맞으면 건너뛴다. 무조건 ALTER하면 기동마다 테이블을 재작성한다.
PREP_SCHEMA_SQL = [
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'prep_vectors'::regclass
              AND attname = 'embedding'
              AND atttypmod <> {settings.EMBEDDING_DIM}
        ) THEN
            -- 차원이 다른 벡터는 유사도 계산이 불가능하므로 보존할 이유가 없다.
            DELETE FROM prep_vectors;
            ALTER TABLE prep_vectors
                ALTER COLUMN embedding TYPE vector({settings.EMBEDDING_DIM});
        END IF;
    END $$;
    """,
]


def ensure_prep_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in PREP_SCHEMA_SQL:
        bind.execute(text(statement))
