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


class ReviewSession(Base):
    """
    [서류 검토 영역] 검토 요청 한 건. 파일 여러 개를 함께 검토한다.

    파일 하나가 곧 검토 한 건이던 구조를 세션/파일로 나눴다.
    정책은 평균 3개(최대 25개)의 서류를 요구하는데, 파일을 하나만 받으면
    "사업자등록증 하나를 올렸더니 24개가 누락됐다"는, 맞지만 쓸모없는 결과가 나온다.

    요건 대조는 파일별이 아니라 '올린 서류 전체' 기준이어야 한다.
    사업자등록증과 소득금액증명을 함께 올리면 둘 다 충족으로 봐야 하기 때문에,
    모든 파일의 청크를 합쳐 요건과 대조한다. 그래서 대조 결과는 세션에 붙는다.
    """
    __tablename__ = "review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="검토를 요청한 사용자")
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=True, index=True, comment="검토 대상 정책 (선택 — 서류 자체 검토는 정책 없이도 가능)")

    # 어디까지 왔나 (폴링으로 진행률을 보여주는 데 쓴다)
    review_status = Column(
        String(20), nullable=False, default="queued",
        comment="검토 진행 단계 (queued, extracting, matching, diagnosing, done, failed)",
    )

    # 요건 대조를 '할 수 있었는가'. 빈 requirement_matches를 '요건을 다 충족했다'로
    # 읽으면 안 되기 때문에 별도로 기록한다.
    #   not_requested       — 정책을 고르지 않았다
    #   no_requirement_data — 정책은 골랐지만 공고에 필수서류가 명시돼 있지 않다 (전체의 63%)
    #   matched             — 실제로 대조했다
    requirement_status = Column(
        String(24), nullable=False, default="not_requested",
        comment="요건 대조 가능 여부 (not_requested, no_requirement_data, matched)",
    )
    requirement_matches = Column(
        JSON, nullable=True,
        comment="요건별 대조 근거 [{document_name, best_similarity, likely_covered, matched_file}]",
    )

    # 세션 전체 종합 진단 (파일별 진단은 ReviewUpload.diagnosis에 있다)
    summary = Column(Text, nullable=True, comment="올린 서류 전체에 대한 종합 진단 한두 문장")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    uploads = relationship(
        "ReviewUpload",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReviewUpload.created_at",
    )
    policy = relationship("NormalizedPolicy")


class ReviewUpload(Base):
    """
    [서류 검토 영역] 검토 세션에 포함된 파일 하나.

    - 정책 첨부(attachment_files)와 의미가 다르므로 테이블을 분리한다.
      (attachment_files = 기관이 게시한 공고 첨부, review_uploads = 사용자 제출 서류)
    - 파일별 진단(오타·빈칸·형식)은 여기에, 요건 대조는 세션에 붙는다.
    """
    __tablename__ = "review_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="이 파일이 속한 검토 세션",
    )

    original_file_name = Column(Text, nullable=True, comment="원본 파일명")
    storage_path = Column(Text, nullable=False, comment="업로드 파일 저장 경로")
    content_type = Column(String(100), nullable=True, comment="파일 MIME 타입")
    file_size = Column(BigInteger, nullable=True, comment="파일 크기 (Byte)")

    extracted_text = Column(Text, nullable=True, comment="kordoc으로 추출된 서류 본문")
    # '왜 못 읽었나'를 사용자에게 안내하기 위한 원인. review_status(진행 단계)와는 다른 질문이다.
    extraction_status = Column(String(30), nullable=False, default="pending", comment="추출 상태 (pending, success, empty, unsupported, failed)")

    diagnosis = Column(
        JSON, nullable=True,
        comment="이 파일 자체의 진단 {document_type, typos[], missing_fields[], format_issues[], improvement_points[], overall}",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    session = relationship("ReviewSession", back_populates="uploads")


# 구 review_uploads 정리. create_all() '이전에' 실행한다.
#
# 파일 하나가 곧 검토 한 건이던 구조를 세션/파일로 나누면서, review_uploads가 들고 있던
# policy_id·review_status·requirement_matches가 review_sessions로 옮겨갔다. 구 테이블과
# 새 정의는 호환되지 않는다(session_id NOT NULL이 붙는다).
#
# 무조건 DROP하면 기동마다 검토 이력이 날아간다. 구 스키마에만 있던 컬럼(policy_id)을
# 지문 삼아, 옛 테이블일 때만 한 번 버린다. 새 테이블에는 이 컬럼이 없으므로 두 번 다시
# 실행되지 않는다(멱등).
REVIEW_LEGACY_CLEANUP_SQL = [
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'review_uploads' AND column_name = 'policy_id'
        ) THEN
            DROP TABLE review_uploads CASCADE;
        END IF;
    END $$;
    """,
]


# 이미 생성된 테이블에 컬럼/인덱스를 덧붙이는 패치. create_all() '이후'에 실행한다.
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
    # 서버가 재시작되면 진행 중이던 검토는 살아남지 못한다. BackgroundTasks는 프로세스 안에서
    # 돌기 때문에, 남은 행을 queued로 되돌려봐야 주워갈 워커가 없다 — 사용자는 '대기 중'을
    # 영원히 보게 된다. 정직하게 실패로 표시하고 다시 시도하도록 안내한다.
    """
    UPDATE review_sessions
       SET review_status = 'failed',
           summary = COALESCE(summary, '서버가 재시작되어 검토가 중단되었습니다. 다시 시도해주세요.')
     WHERE review_status IN ('queued', 'extracting', 'matching', 'diagnosing')
    """,
]


def ensure_review_legacy_cleanup(bind) -> None:
    """구 review_uploads를 정리한다. 반드시 create_all() 이전에 호출할 것."""
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in REVIEW_LEGACY_CLEANUP_SQL:
        bind.execute(text(statement))


def ensure_review_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in REVIEW_SCHEMA_SQL:
        bind.execute(text(statement))
