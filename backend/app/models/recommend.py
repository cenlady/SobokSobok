import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base

class RecommendationVector(Base):
    """
    [추천 API 영역] 사용자 맞춤 정책 추천용 벡터 테이블
    - 역할: 사용자의 프로필 조건 정보를 임베딩화한 벡터와 정책들의 지원 대상을 비교 추천하기 위해 사용되는 벡터들을 보관합니다.
    - 소유자: 추천 서비스
    - 벡터 규약: 사용자 설정에 따라 embedding_openai 또는 embedding_ollama를 검색합니다.
    """
    __tablename__ = "rec_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, index=True, comment="정규화 공고 ID 참조")
    vector_type = Column(String(50), nullable=False, default="policy_recommendation", comment="추천 벡터 유형")
    source_text = Column(Text, nullable=False, comment="LangChain Document.page_content에 해당하는 추천용 대표 텍스트")
    source_hash = Column(String(64), nullable=False, comment="source_text 변경 감지용 SHA-256 해시")
    embedding_provider = Column(String(30), nullable=False, default="openai+ollama", comment="저장된 임베딩 제공자")
    embedding_model = Column(String(100), nullable=False, comment="임베딩 모델명")
    embedding_dim = Column(Integer, nullable=False, comment="저장 벡터 차원")
    embedding_status = Column(String(30), nullable=False, default="pending", comment="pending/success/failed")
    embedding_error = Column(Text, nullable=True, comment="임베딩 실패 메시지")
    vector_metadata = Column("metadata", JSON, nullable=False, default=dict, comment="LangChain Document.metadata에 해당하는 필터 메타데이터")
    
    # 추천 전용 pgvector 임베딩 벡터. 챗과 같은 기본 1536차원이지만 테이블은 분리한다.
    embedding_openai = Column(
        Vector(settings.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="[pgvector] 클라우드 AI 추천 검색용 OpenAI 벡터",
    )
    embedding_ollama = Column(
        Vector(settings.RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="[pgvector] 로컬 AI 추천 검색용 Ollama 벡터",
    )
    embedding_openai_model = Column(String(100), nullable=True)
    embedding_ollama_model = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("policy_id", "vector_type", name="uk_rec_vectors_policy_type"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy")


RECOMMENDATION_VECTOR_SCHEMA_SQL = [
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS vector_type VARCHAR(50) NOT NULL DEFAULT 'policy_recommendation'",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS source_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64) NOT NULL DEFAULT ''",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_provider VARCHAR(30) NOT NULL DEFAULT 'openai+ollama'",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_dim INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(30) NOT NULL DEFAULT 'pending'",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_error TEXT",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS metadata JSON NOT NULL DEFAULT '{}'::json",
    f"ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_openai vector({settings.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS})",
    f"ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_ollama vector({settings.RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS})",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_openai_model VARCHAR(100)",
    "ALTER TABLE rec_vectors ADD COLUMN IF NOT EXISTS embedding_ollama_model VARCHAR(100)",
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'rec_vectors'::regclass
              AND (
                    (attname = 'embedding_openai' AND atttypmod <> {settings.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS})
                 OR (attname = 'embedding_ollama' AND atttypmod <> {settings.RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS})
              )
        ) THEN
            DELETE FROM rec_vectors;
            ALTER TABLE rec_vectors
                ALTER COLUMN embedding_openai TYPE vector({settings.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS});
            ALTER TABLE rec_vectors
                ALTER COLUMN embedding_ollama TYPE vector({settings.RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS});
        END IF;
    END $$;
    """,
    "ALTER TABLE rec_vectors DROP COLUMN IF EXISTS embedding",
    "ALTER TABLE rec_vectors DROP CONSTRAINT IF EXISTS rec_vectors_policy_id_key",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uk_rec_vectors_policy_type'
        ) THEN
            ALTER TABLE rec_vectors ADD CONSTRAINT uk_rec_vectors_policy_type UNIQUE (policy_id, vector_type);
        END IF;
    END $$;
    """,
    "CREATE INDEX IF NOT EXISTS idx_rec_vectors_policy_id ON rec_vectors (policy_id)",
    "CREATE INDEX IF NOT EXISTS idx_rec_vectors_type_status ON rec_vectors (vector_type, embedding_status)",
    "CREATE INDEX IF NOT EXISTS idx_rec_vectors_metadata_gin ON rec_vectors USING gin ((metadata::jsonb))",
]


def ensure_recommendation_vector_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in RECOMMENDATION_VECTOR_SCHEMA_SQL:
        bind.execute(text(statement))
