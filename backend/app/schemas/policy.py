from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    pbanc_sn: int
    file_name: str
    file_size: int | None = None
    saved_path: str | None = None
    file_hash: str | None = None


class PolicyAnnouncementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pbanc_sn: int
    source: str
    title: str
    target: str | None = None
    category: str | None = None
    organization: str | None = None
    apply_start: str | None = None
    apply_end: str | None = None
    status: str | None = None
    detail_url: str
    content_text: str | None = None
    content_hash: str


class PolicyProgramPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_url: str
    category: str | None = None
    program_name: str
    content_text: str | None = None
    content_hash: str


class PolicyProgramPageDetailRead(PolicyProgramPageRead):
    content_html: str | None = None
    sections_json: list[dict[str, str]] | None = None
    raw_breadcrumbs_json: list[str] | None = None


class PolicyAnnouncementDetailRead(PolicyAnnouncementRead):
    content_html: str | None = None
    attachments: list[PolicyAttachmentRead] = []


class NormalizedPolicyAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attachment_file_id: UUID
    original_file_name: str | None = None


class NormalizedPolicyDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    source_pk: str
    title: str
    summary: str | None = None
    body: str | None = None
    organization: str | None = None
    support_type: str | None = None
    target_text: str | None = None
    support_content: str | None = None
    region_scope: str
    sido: str | None = None
    sigungu: str | None = None
    matched_sidos: list[str] = Field(default_factory=list)
    status: str | None = None
    apply_start: datetime | None = None
    apply_end: datetime | None = None
    apply_url: str | None = None
    application_methods: list[str] = Field(default_factory=list)
    contact_points: list[Any] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    business_status_tags: list[str] = Field(default_factory=list)
    eligibility: dict[str, Any] = Field(default_factory=dict)
    required_documents: list[Any] = Field(default_factory=list)
    attachments: list[NormalizedPolicyAttachmentRead] = Field(default_factory=list)
