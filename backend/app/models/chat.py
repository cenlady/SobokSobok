import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_hash = Column(String(255), nullable=False)
    chunk_metadata = Column("metadata", JSON, nullable=False)
    embedding_status = Column(String(30), nullable=False, default="pending")
    embedding_model = Column(Text, nullable=True)
    
    # pgvector 1536 차원 벡터 정의 (기본값)
    embedding = Column(Vector(1536), nullable=True)
    
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_hash", name="uk_policy_chunks_hash"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="chunks")
    document = relationship("PolicyDocument", back_populates="chunks")
