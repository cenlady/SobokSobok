from pydantic import BaseModel, ConfigDict


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
