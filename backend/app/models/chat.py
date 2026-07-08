import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base

class PolicyChunk(Base):
    """
    [RAG 챗봇 영역] 텍스트 청크 및 벡터 임베딩 테이블
    - 역할: 공고 상세 요건 문서(PolicyDocument)들을 RAG 모델 크기에 맞게 쪼갠 청크와 벡터를 관리합니다.
    - 소유자: 챗봇 RAG 서비스
    - 벡터 규약: 이 테이블의 'embedding' 필드를 사용하여 사용자 질문의 임베딩 벡터와 유사도 검색(Cosine Distance 등)을 수행합니다.
    """
    __tablename__ = "policy_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, index=True, comment="정규화 공고 ID 참조")
    document_id = Column(UUID(as_uuid=True), ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True, comment="요건 문서 ID 참조")
    chunk_index = Column(Integer, nullable=False, comment="쪼개진 순서 인덱스 (0, 1, 2...)")
    chunk_text = Column(Text, nullable=False, comment="쪼개진 텍스트 본문 (청크)")
    chunk_hash = Column(String(255), nullable=False, comment="청크 텍스트 중복 방지용 해시")
    chunk_metadata = Column("metadata", JSON, nullable=False, comment="청크 메타데이터 (토큰수, 생성 모델 정보 등)")
    embedding_status = Column(String(30), nullable=False, default="pending", comment="임베딩 처리 상태 (pending, success, failed)")
    embedding_model = Column(Text, nullable=True, comment="임베딩에 사용한 인공지능 모델명")
    
    # pgvector 임베딩 벡터 (차원은 settings.EMBEDDING_DIM으로 관리)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True, comment="[pgvector] 청크 임베딩 벡터값")
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_hash", name="uk_policy_chunks_hash"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="chunks")
    document = relationship("PolicyDocument", back_populates="chunks")
