import uuid
from sqlalchemy import Column, DateTime, ForeignKey, func
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
    - 벡터 규약: 이 테이블의 'embedding' 필드를 사용하여 사용자의 맞춤형 추천 유사도 검색을 수행합니다.
    """
    __tablename__ = "rec_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, unique=True, comment="정규화 공고 ID 참조 (1:1 대응)")
    
    # pgvector 임베딩 벡터 (차원은 settings.EMBEDDING_DIM으로 관리)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False, comment="[pgvector] 추천용 정책 매칭 임베딩 벡터값")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    policy = relationship("NormalizedPolicy")
