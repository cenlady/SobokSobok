from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PolicyAnnouncement(Base):
    __tablename__ = "policy_announcements"

    # Sbiz24 공고 고유번호이며 첨부파일 테이블의 FK 기준이 된다.
    pbanc_sn = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default="sbiz24", index=True)
    title = Column(String(500), nullable=False)
    target = Column(String(200), nullable=True, index=True)
    category = Column(String(200), nullable=True, index=True)
    organization = Column(String(300), nullable=True)
    apply_start = Column(String(50), nullable=True)
    apply_end = Column(String(50), nullable=True, index=True)
    status = Column(String(100), nullable=True, index=True)
    detail_url = Column(String(500), nullable=False)
    content_html = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    raw_list_json = Column(JSON, nullable=True)
    raw_detail_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)

    attachments = relationship(
        "PolicyAttachment",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PolicyAttachment(Base):
    __tablename__ = "policy_attachments"

    # 파일 bytes는 디스크에 저장하고, DB에는 파일 고유번호와 경로/해시만 저장한다.
    file_id = Column(String(100), primary_key=True)
    pbanc_sn = Column(
        Integer,
        ForeignKey("policy_announcements.pbanc_sn", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    saved_path = Column(String(1000), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    raw_file_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    downloaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    announcement = relationship(
        "PolicyAnnouncement",
        back_populates="attachments",
    )


class PolicyProgramPage(Base):
    __tablename__ = "policy_program_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, default="semas", index=True)
    source_url = Column(String(1000), nullable=False, unique=True, index=True)
    category = Column(String(300), nullable=True, index=True)
    program_name = Column(String(500), nullable=False, index=True)
    content_html = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    sections_json = Column(JSON, nullable=True)
    raw_breadcrumbs_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
