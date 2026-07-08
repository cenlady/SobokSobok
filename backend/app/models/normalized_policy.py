import uuid
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, BigInteger, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base

class NormalizedPolicy(Base):
    __tablename__ = "normalized_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(30), nullable=False)
    source_pk = Column(String(200), nullable=False)
    canonical_key = Column(Text, nullable=False)
    duplicate_group_key = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    organization = Column(Text, nullable=True)
    support_type = Column(String(100), nullable=True)
    target_text = Column(Text, nullable=True)
    support_content = Column(Text, nullable=True)
    region_scope = Column(String(20), nullable=False, default="unknown")
    sido = Column(String(50), nullable=True)
    sigungu = Column(String(50), nullable=True)
    status = Column(String(30), nullable=True)
    apply_start = Column(DateTime, nullable=True)
    apply_end = Column(DateTime, nullable=True)
    apply_url = Column(Text, nullable=True)
    industry_tags = Column(JSON, nullable=False)
    business_status_tags = Column(JSON, nullable=False)
    eligibility = Column(JSON, nullable=False)
    required_documents = Column(JSON, nullable=False)
    source_content_hash = Column(Text, nullable=True)
    normalized_hash = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "source_pk", name="uk_normalized_policies_source"),
    )

    # Relationships
    attachments = relationship("PolicyAttachmentLink", back_populates="policy", cascade="all, delete-orphan")
    documents = relationship("PolicyDocument", back_populates="policy", cascade="all, delete-orphan")
    chunks = relationship("PolicyChunk", back_populates="policy", cascade="all, delete-orphan")


class AttachmentFile(Base):
    __tablename__ = "attachment_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_hash = Column(String(255), nullable=False, unique=True)
    storage_path = Column(Text, nullable=False)
    original_file_name = Column(Text, nullable=True)
    content_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    extracted_text = Column(Text, nullable=True)
    extraction_status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False)

    # Relationships
    policy_links = relationship("PolicyAttachmentLink", back_populates="file", cascade="all, delete-orphan")


class PolicyAttachmentLink(Base):
    __tablename__ = "policy_attachment_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False)
    attachment_file_id = Column(UUID(as_uuid=True), ForeignKey("attachment_files.id", ondelete="CASCADE"), nullable=False)
    source_file_id = Column(Text, nullable=True)
    original_file_name = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("policy_id", "attachment_file_id", name="uk_policy_attachment_links"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="attachments")
    file = relationship("AttachmentFile", back_populates="policy_links")


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(30), nullable=False)
    source_ref = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    text = Column(Text, nullable=False)
    text_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("policy_id", "document_type", "text_hash", name="uk_policy_documents_hash"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="documents")
    chunks = relationship("PolicyChunk", back_populates="document", cascade="all, delete-orphan")
