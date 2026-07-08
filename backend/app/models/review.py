import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base

class ReviewVector(Base):
    """
    [서류 검토 영역] 제출 서류 요건 검토 및 요건 대조용 벡터 테이블
    - 역할: 정책의 필수 제출 서류 요건(`required_documents`) 텍스트의 벡터값 및 사용자 제출 문서 검토 시 비교 대상으로 사용할 수 있는 요건 임베딩 데이터를 보관합니다.
    - 소유자: 서류 검토 서비스
    """
    __tablename__ = "review_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, comment="정규화 공고 ID 참조")
    document_name = Column(String(255), nullable=False, comment="대조 대상 필수 구비 서류 명칭")
    
    # pgvector 임베딩 벡터 (차원은 settings.EMBEDDING_DIM으로 관리)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False, comment="[pgvector] 요건 대조 임베딩 벡터값")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    policy = relationship("NormalizedPolicy")
