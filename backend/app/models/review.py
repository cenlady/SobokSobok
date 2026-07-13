import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base


class ReviewVector(Base):
    """
    [서류 검토 영역] 제출 서류 요건 검토 및 요건 대조용 벡터 테이블
    - 역할: 정책의 필수 제출 서류 요건(`required_documents`) 및 지원대상 요건 텍스트의
      임베딩을 보관하여, 사용자가 업로드한 서류 내용과 대조하는 데 사용합니다.
    - 소유자: 서류 검토 서비스 (공유 계약 #1: 벡터는 각자 소유)
    - 임베딩: Ollama bge-m3 (1024차원). 차원은 settings.REVIEW_EMBEDDING_DIM으로 관리.
    """
    __tablename__ = "review_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, index=True, comment="정규화 공고 ID 참조")
    document_name = Column(String(255), nullable=False, comment="대조 대상 필수 구비 서류 명칭")
    document_type = Column(String(30), nullable=False, default="required_document", comment="요건 유형 (required_document, eligibility 등)")
    source_text = Column(Text, nullable=True, comment="임베딩 원문. 검색 후 LLM 진단에 근거로 넘긴다")

    # pgvector 임베딩 벡터 (차원은 settings.REVIEW_EMBEDDING_DIM으로 관리)
    embedding = Column(Vector(settings.REVIEW_EMBEDDING_DIM), nullable=False, comment="[pgvector] 요건 대조 임베딩 벡터값")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("policy_id", "document_type", "document_name", name="uk_review_vectors_policy_doc"),
        Index("idx_review_vectors_policy_type", "policy_id", "document_type"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy")


class ReviewUpload(Base):
    """
    [서류 검토 영역] 사용자가 업로드한 검토 대상 서류
    - 역할: 업로드 파일의 물리 경로, 추출 텍스트, 진단 결과를 보관합니다.
    - 정책 첨부(attachment_files)와 의미가 다르므로 테이블을 분리한다.
      (attachment_files = 기관이 게시한 공고 첨부, review_uploads = 사용자 제출 서류)
    """
    __tablename__ = "review_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="업로드한 사용자 (미인증 데모 허용 위해 nullable)")
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=True, index=True, comment="검토 대상 정책 (선택 — 서류 자체 검토는 정책 없이도 가능)")

    original_file_name = Column(Text, nullable=True, comment="원본 파일명")
    storage_path = Column(Text, nullable=False, comment="업로드 파일 저장 경로")
    content_type = Column(String(100), nullable=True, comment="파일 MIME 타입")
    file_size = Column(BigInteger, nullable=True, comment="파일 크기 (Byte)")

    extracted_text = Column(Text, nullable=True, comment="kordoc/OCR로 추출된 서류 본문")
    extraction_status = Column(String(30), nullable=False, default="pending", comment="추출 상태 (pending, success, empty, unsupported, failed)")

    # review_status와 extraction_status는 서로 다른 것을 말한다.
    #   review_status     = 어디까지 왔나 (진행 단계) — 폴링으로 진행률을 보여주는 데 쓴다
    #   extraction_status = 왜 못 읽었나 (실패 원인) — 사용자에게 사유를 안내하는 데 쓴다
    # 하나로 합치면 "요건 대조 중"과 "AI 진단 중"을 구분할 수 없어 가짜 진행률이 된다.
    review_status = Column(
        String(20), nullable=False, default="queued",
        comment="검토 진행 단계 (queued, extracting, matching, diagnosing, done, failed)",
    )

    diagnosis = Column(JSON, nullable=True, comment="LLM 진단 결과 {document_type, typos[], missing_fields[], format_issues[], improvement_points[], overall}")
    # 비동기 폴링에서는 결과를 나중에 조회하므로, 메모리로만 반환하면 요건 대조 근거가 유실된다.
    requirement_matches = Column(
        JSON, nullable=True,
        comment="요건별 임베딩 대조 근거 [{document_name, best_similarity, likely_covered}]",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    policy = relationship("NormalizedPolicy")


# 이미 생성된 DB에 신규 컬럼/인덱스를 무중단 반영하기 위한 패치 SQL.
# create_all()은 기존 테이블에 컬럼을 추가하지 않으므로 서버 시작 시 함께 실행한다.
REVIEW_SCHEMA_SQL = [
    "ALTER TABLE review_vectors ADD COLUMN IF NOT EXISTS document_type VARCHAR(30) NOT NULL DEFAULT 'required_document'",
    "ALTER TABLE review_vectors ADD COLUMN IF NOT EXISTS source_text TEXT",
    # 차원이 이미 맞으면 건너뛴다. 무조건 ALTER하면 기동마다 테이블을 재작성한다.
    # (기존 벡터는 차원이 달라 무의미하므로 변경 전에 비운다.)
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'review_vectors'::regclass
              AND attname = 'embedding'
              AND atttypmod <> {settings.REVIEW_EMBEDDING_DIM}
        ) THEN
            DELETE FROM review_vectors;
            ALTER TABLE review_vectors
                ALTER COLUMN embedding TYPE vector({settings.REVIEW_EMBEDDING_DIM});
        END IF;
    END $$;
    """,
    "CREATE INDEX IF NOT EXISTS idx_review_vectors_policy_type ON review_vectors (policy_id, document_type)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uk_review_vectors_policy_doc ON review_vectors (policy_id, document_type, document_name)",
    # 서류 자체 검토로 전환하며 policy_id를 선택으로 변경 (#23)
    "ALTER TABLE review_uploads ALTER COLUMN policy_id DROP NOT NULL",
    # 비동기 검토 전환 (#31)
    "ALTER TABLE review_uploads ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) NOT NULL DEFAULT 'queued'",
    "ALTER TABLE review_uploads ADD COLUMN IF NOT EXISTS requirement_matches JSON",
    # 서버가 재시작되면 진행 중이던 검토는 살아남지 못한다. BackgroundTasks는 프로세스 안에서
    # 돌기 때문에, 남은 행을 queued로 되돌려봐야 주워갈 워커가 없다 — 사용자는 '대기 중'을
    # 영원히 보게 된다. 정직하게 실패로 표시하고 다시 시도하도록 안내한다.
    """
    UPDATE review_uploads
       SET review_status = 'failed',
           diagnosis = COALESCE(diagnosis, '{
               "document_type": "unknown",
               "typos": [], "missing_fields": [], "format_issues": [],
               "missing_documents": [], "improvement_points": [],
               "overall": "서버가 재시작되어 검토가 중단되었습니다. 다시 시도해주세요."
           }'::json)
     WHERE review_status IN ('queued', 'extracting', 'matching', 'diagnosing')
    """,
]


def ensure_review_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in REVIEW_SCHEMA_SQL:
        bind.execute(text(statement))
