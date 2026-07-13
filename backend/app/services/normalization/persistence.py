from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.normalized_policy import (
    AttachmentFile,
    NormalizedPolicy,
    PolicyAttachmentLink,
    PolicyDocument,
)
from app.models.policy import PolicyAttachment
from app.services.normalization.common import _clean_text, _make_hash

def _upsert_policy(db: Session, payload: dict[str, Any]) -> tuple[NormalizedPolicy, str]:
    payload = dict(payload)
    payload["normalized_hash"] = _make_hash(
        {key: value for key, value in payload.items() if key != "normalized_hash"}
    )
    policy = (
        db.query(NormalizedPolicy)
        .filter(
            NormalizedPolicy.source == payload["source"],
            NormalizedPolicy.source_pk == payload["source_pk"],
        )
        .one_or_none()
    )
    if policy is None:
        policy = NormalizedPolicy(**payload)
        db.add(policy)
        db.flush()
        return policy, "created"

    if policy.normalized_hash == payload["normalized_hash"]:
        return policy, "unchanged"

    for key, value in payload.items():
        setattr(policy, key, value)
    db.flush()
    return policy, "updated"


def _replace_documents(
    db: Session,
    policy: NormalizedPolicy,
    documents: list[dict[str, str | None]],
) -> int:
    created = 0
    incoming_documents: dict[tuple[str, str], dict[str, str | None]] = {}
    seen: set[tuple[str, str]] = set()
    for document in documents:
        text_value = _clean_text(document.get("text"))
        if not text_value:
            continue
        document_type = document.get("document_type") or "body"
        text_hash = _make_hash(text_value)
        key = (document_type, text_hash)
        if key in seen:
            continue
        seen.add(key)
        incoming_documents[key] = {
            "document_type": document_type,
            "source_ref": document.get("source_ref"),
            "title": document.get("title"),
            "text": text_value,
            "text_hash": text_hash,
        }

    existing_documents = {
        (document.document_type, document.text_hash): document
        for document in list(policy.documents)
    }

    # 동일한 document_type + text_hash 문서는 그대로 유지합니다.
    # document_id가 보존되어야 policy_chunks FK와 기존 임베딩도 함께 살아남습니다.
    for key, payload in incoming_documents.items():
        existing_document = existing_documents.get(key)
        if existing_document is not None:
            # 본문이 같은 문서라도 제목/source_ref는 크롤링 데이터 보정으로 바뀔 수 있으므로 갱신합니다.
            existing_document.source_ref = payload["source_ref"]
            existing_document.title = payload["title"]
            continue

        db.add(
            PolicyDocument(
                policy_id=policy.id,
                document_type=payload["document_type"],
                source_ref=payload["source_ref"],
                title=payload["title"],
                text=payload["text"],
                text_hash=payload["text_hash"],
            )
        )
        created += 1

    # 새 정규화 결과에서 사라진 문서만 삭제합니다.
    # 이 경우에만 연결된 policy_chunks가 cascade 삭제되는 것이 의도된 동작입니다.
    incoming_keys = set(incoming_documents.keys())
    for key, existing_document in existing_documents.items():
        if key not in incoming_keys:
            db.delete(existing_document)

    db.flush()
    return created


def _sync_sbiz24_attachments(
    db: Session,
    policy: NormalizedPolicy,
    attachments: list[PolicyAttachment],
) -> dict[str, int]:
    stats = {"attachments_created": 0, "attachment_links_created": 0}
    existing_links = {
        link.source_file_id
        for link in policy.attachments
        if link.source_file_id
    }

    for order, attachment in enumerate(attachments):
        file_hash = attachment.file_hash or _make_hash(attachment.file_id)
        storage_path = attachment.saved_path or ""
        if not storage_path:
            continue
        file_row = (
            db.query(AttachmentFile)
            .filter(AttachmentFile.file_hash == file_hash)
            .one_or_none()
        )
        if file_row is None:
            file_row = AttachmentFile(
                file_hash=file_hash,
                storage_path=storage_path,
                original_file_name=attachment.file_name,
                content_type=_guess_content_type(attachment.file_name),
                file_size=attachment.file_size,
                extracted_text=None,
                extraction_status="pending",
            )
            db.add(file_row)
            db.flush()
            stats["attachments_created"] += 1

        if attachment.file_id in existing_links:
            continue
        db.add(
            PolicyAttachmentLink(
                policy_id=policy.id,
                attachment_file_id=file_row.id,
                source_file_id=attachment.file_id,
                original_file_name=attachment.file_name,
                display_order=order,
            )
        )
        stats["attachment_links_created"] += 1

    return stats
def _guess_content_type(file_name: str) -> str | None:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    if not suffix:
        return None
    return {
        "pdf": "application/pdf",
        "hwp": "application/x-hwp",
        "hwpx": "application/hwp+zip",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, suffix)
