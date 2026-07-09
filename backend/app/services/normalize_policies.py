from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.gov24 import Gov24ServiceDetail, Gov24ServiceList, Gov24SupportCondition
from app.models.normalized_policy import (
    AttachmentFile,
    NormalizedPolicy,
    PolicyAttachmentLink,
    PolicyDocument,
)
from app.models.policy import PolicyAnnouncement, PolicyAttachment, PolicyProgramPage


def normalize_policy_sources_once() -> dict[str, int | bool]:
    db = SessionLocal()
    locked = False
    stats: dict[str, int | bool] = {
        "locked": False,
        "normalized_created": 0,
        "normalized_updated": 0,
        "normalized_unchanged": 0,
        "documents_created": 0,
        "attachments_created": 0,
        "attachment_links_created": 0,
        "errors": 0,
    }

    try:
        locked = _try_advisory_lock(db)
        stats["locked"] = locked
        if not locked:
            return stats

        for normalizer in (
            _normalize_sbiz24,
            _normalize_semas,
            _normalize_gov24,
        ):
            try:
                _merge_stats(stats, normalizer(db))
            except Exception as exc:
                db.rollback()
                stats["errors"] = int(stats["errors"]) + 1
                print(f"[normalizer] source failed: {exc}", flush=True)

        return stats
    finally:
        if locked:
            _release_advisory_lock(db)
        db.close()


def _normalize_sbiz24(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    rows = (
        db.query(PolicyAnnouncement)
        .options(selectinload(PolicyAnnouncement.attachments))
        .filter(PolicyAnnouncement.is_active.is_(True))
        .all()
    )

    for row in rows:
        docs = _sbiz24_documents(row)
        payload = {
            "source": "sbiz24",
            "source_pk": str(row.pbanc_sn),
            "canonical_key": f"sbiz24:{row.pbanc_sn}",
            "duplicate_group_key": _duplicate_group_key(row.title, row.organization),
            "title": row.title,
            "summary": _summarize(row.content_text) or row.title,
            "body": row.content_text,
            "organization": row.organization,
            "support_type": row.category,
            "target_text": row.target,
            "support_content": row.content_text,
            "region_scope": "unknown",
            "sido": None,
            "sigungu": None,
            "status": _normalize_status(row.status),
            "apply_start": _parse_datetime(row.apply_start),
            "apply_end": _parse_datetime(row.apply_end),
            "apply_url": row.detail_url,
            "industry_tags": _compact_list([row.category]),
            "business_status_tags": _business_tags_from_text(row.target or ""),
            "eligibility": {
                "source": "sbiz24",
                "target": row.target,
                "category": row.category,
                "status_raw": row.status,
                "apply_start_raw": row.apply_start,
                "apply_end_raw": row.apply_end,
            },
            "required_documents": [],
            "source_content_hash": row.content_hash,
            "is_active": row.is_active,
        }

        policy, action = _upsert_policy(db, payload)
        stats[f"normalized_{action}"] += 1
        if action != "unchanged" or not policy.documents:
            stats["documents_created"] += _replace_documents(db, policy, docs)
        file_stats = _sync_sbiz24_attachments(db, policy, row.attachments)
        _merge_stats(stats, file_stats)
        db.commit()

    return stats


def _normalize_semas(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    rows = (
        db.query(PolicyProgramPage)
        .filter(PolicyProgramPage.is_active.is_(True))
        .all()
    )

    for row in rows:
        source_pk = _stable_short_key(row.source_url)
        docs = _semas_documents(row)
        payload = {
            "source": "semas",
            "source_pk": source_pk,
            "canonical_key": f"semas:{source_pk}",
            "duplicate_group_key": _duplicate_group_key(row.program_name, "소상공인시장진흥공단"),
            "title": row.program_name,
            "summary": _summarize(row.content_text) or row.program_name,
            "body": row.content_text,
            "organization": "소상공인시장진흥공단",
            "support_type": row.category,
            "target_text": None,
            "support_content": row.content_text,
            "region_scope": "unknown",
            "sido": None,
            "sigungu": None,
            "status": "notice",
            "apply_start": None,
            "apply_end": None,
            "apply_url": row.source_url,
            "industry_tags": _compact_list([row.category]),
            "business_status_tags": ["small_business"],
            "eligibility": {
                "source": "semas",
                "source_url": row.source_url,
                "category": row.category,
                "breadcrumbs": row.raw_breadcrumbs_json or [],
            },
            "required_documents": [],
            "source_content_hash": row.content_hash,
            "is_active": row.is_active,
        }

        policy, action = _upsert_policy(db, payload)
        stats[f"normalized_{action}"] += 1
        if action != "unchanged" or not policy.documents:
            stats["documents_created"] += _replace_documents(db, policy, docs)
        db.commit()

    return stats


def _normalize_gov24(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    list_rows = (
        db.query(Gov24ServiceList)
        .filter(Gov24ServiceList.is_active.is_(True))
        .all()
    )

    for list_row in list_rows:
        detail = db.get(Gov24ServiceDetail, list_row.service_id)
        condition = db.get(Gov24SupportCondition, list_row.service_id)
        docs_required = _required_documents_from_gov24(detail)
        target_text = _first_text(
            detail.support_target if detail else None,
            list_row.support_target,
        )
        support_content = _first_text(
            detail.support_content if detail else None,
            list_row.support_content,
        )
        body = _join_sections(
            [
                ("서비스 목적", _first_text(detail.service_purpose if detail else None, list_row.service_purpose_summary)),
                ("지원 대상", target_text),
                ("지원 내용", support_content),
                ("선정 기준", _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria)),
                ("신청 방법", _first_text(detail.application_method if detail else None, list_row.application_method)),
                ("구비 서류", detail.required_docs if detail else None),
                ("신청 기한", _first_text(detail.application_deadline if detail else None, list_row.application_deadline)),
            ]
        )
        application_deadline = _first_text(
            detail.application_deadline if detail else None,
            list_row.application_deadline,
        )
        apply_start, apply_end = _parse_deadline_range(application_deadline)
        condition_payload = _condition_payload(condition)
        docs = _gov24_documents(
            body=body,
            target_text=target_text,
            support_content=support_content,
            required_docs=docs_required,
            application_method=_first_text(detail.application_method if detail else None, list_row.application_method),
            selection_criteria=_first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
        )
        source_hash = _make_hash(
            [
                list_row.content_hash,
                detail.content_hash if detail else None,
                condition.content_hash if condition else None,
            ]
        )
        payload = {
            "source": "gov24",
            "source_pk": list_row.service_id,
            "canonical_key": f"gov24:{list_row.service_id}",
            "duplicate_group_key": _duplicate_group_key(list_row.service_name, list_row.organization_name),
            "title": list_row.service_name,
            "summary": _first_text(list_row.service_purpose_summary, _summarize(support_content), list_row.service_name),
            "body": body,
            "organization": _first_text(detail.organization_name if detail else None, list_row.organization_name),
            "support_type": _first_text(detail.support_type if detail else None, list_row.support_type, list_row.service_field),
            "target_text": target_text,
            "support_content": support_content,
            "region_scope": "national",
            "sido": None,
            "sigungu": None,
            "status": _status_from_deadline(application_deadline),
            "apply_start": apply_start,
            "apply_end": apply_end,
            "apply_url": _first_text(detail.online_application_url if detail else None, list_row.detail_url),
            "industry_tags": condition_payload["industry_tags"],
            "business_status_tags": condition_payload["business_status_tags"],
            "eligibility": {
                "source": "gov24",
                "user_type": list_row.user_type,
                "service_field": list_row.service_field,
                "selection_criteria": _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                "application_deadline": application_deadline,
                "support_conditions": condition_payload["raw_flags"],
            },
            "required_documents": docs_required,
            "source_content_hash": source_hash,
            "is_active": list_row.is_active,
        }

        policy, action = _upsert_policy(db, payload)
        stats[f"normalized_{action}"] += 1
        if action != "unchanged" or not policy.documents:
            stats["documents_created"] += _replace_documents(db, policy, docs)
        db.commit()

    return stats


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
    for document in list(policy.documents):
        db.delete(document)
    db.flush()

    created = 0
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
        db.add(
            PolicyDocument(
                policy_id=policy.id,
                document_type=document_type,
                source_ref=document.get("source_ref"),
                title=document.get("title"),
                text=text_value,
                text_hash=text_hash,
            )
        )
        created += 1
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


def _sbiz24_documents(row: PolicyAnnouncement) -> list[dict[str, str | None]]:
    return [
        {
            "document_type": "body",
            "source_ref": f"policy_announcements:{row.pbanc_sn}:content_text",
            "title": row.title,
            "text": row.content_text,
        },
        {
            "document_type": "application",
            "source_ref": f"policy_announcements:{row.pbanc_sn}:apply_period",
            "title": "신청 기간",
            "text": _join_text([row.apply_start, row.apply_end, row.status]),
        },
    ]


def _semas_documents(row: PolicyProgramPage) -> list[dict[str, str | None]]:
    documents = [
        {
            "document_type": "body",
            "source_ref": f"policy_program_pages:{row.id}:content_text",
            "title": row.program_name,
            "text": row.content_text,
        }
    ]
    for index, section in enumerate(row.sections_json or []):
        if not isinstance(section, dict):
            continue
        documents.append(
            {
                "document_type": "section",
                "source_ref": f"policy_program_pages:{row.id}:sections:{index}",
                "title": _as_text(section.get("title")),
                "text": _as_text(section.get("body") or section.get("text")),
            }
        )
    return documents


def _gov24_documents(
    *,
    body: str | None,
    target_text: str | None,
    support_content: str | None,
    required_docs: list[dict[str, str]],
    application_method: str | None,
    selection_criteria: str | None,
) -> list[dict[str, str | None]]:
    requirement_text = "\n".join(doc["name"] for doc in required_docs)
    return [
        {"document_type": "body", "source_ref": "gov24:body", "title": "정책 본문", "text": body},
        {"document_type": "eligibility", "source_ref": "gov24:support_target", "title": "지원 대상", "text": target_text},
        {"document_type": "eligibility", "source_ref": "gov24:selection_criteria", "title": "선정 기준", "text": selection_criteria},
        {"document_type": "requirements", "source_ref": "gov24:required_docs", "title": "구비 서류", "text": requirement_text},
        {"document_type": "application", "source_ref": "gov24:application_method", "title": "신청 방법", "text": application_method},
        {"document_type": "body", "source_ref": "gov24:support_content", "title": "지원 내용", "text": support_content},
    ]


def _required_documents_from_gov24(detail: Gov24ServiceDetail | None) -> list[dict[str, str]]:
    if detail is None:
        return []
    values = []
    for source, text_value in (
        ("required_docs", detail.required_docs),
        ("required_docs_by_official", detail.required_docs_by_official),
        ("identity_required_docs", detail.identity_required_docs),
    ):
        for line in _split_requirement_lines(text_value):
            if line in {"해당없음", "없음", "해당 없음"}:
                continue
            values.append({"name": line, "description": "", "source": source})
    return _dedupe_dicts(values, "name")


def _condition_payload(condition: Gov24SupportCondition | None) -> dict[str, Any]:
    if condition is None:
        return {
            "industry_tags": [],
            "business_status_tags": [],
            "raw_flags": {},
        }

    industry_map = {
        "ja1201_restaurant_business": "restaurant",
        "ja1202_manufacturing_business": "manufacturing",
        "ja1299_other_business": "other_business",
        "ja2202_company_agriculture_fishery_forestry": "agriculture_fishery_forestry",
        "ja2203_company_information_communication": "information_communication",
        "ja2299_company_other_business": "company_other_business",
    }
    status_map = {
        "ja1101_pre_founder": "pre_founder",
        "ja1102_operating_business": "operating_business",
        "ja1103_closing_business": "closing_business",
        "ja2101_small_medium_business": "small_medium_business",
    }
    raw_flags = {
        column: getattr(condition, column)
        for column in set(industry_map) | set(status_map)
        if getattr(condition, column)
    }
    return {
        "industry_tags": [label for column, label in industry_map.items() if getattr(condition, column)],
        "business_status_tags": [label for column, label in status_map.items() if getattr(condition, column)],
        "raw_flags": raw_flags,
    }


def _empty_stats() -> dict[str, int]:
    return {
        "normalized_created": 0,
        "normalized_updated": 0,
        "normalized_unchanged": 0,
        "documents_created": 0,
        "attachments_created": 0,
        "attachment_links_created": 0,
        "errors": 0,
    }


def _merge_stats(target: dict[str, int | bool], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = int(target.get(key, 0)) + value


def _try_advisory_lock(db: Session) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": settings.NORMALIZER_ADVISORY_LOCK_ID},
        ).scalar()
    )


def _release_advisory_lock(db: Session) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": settings.NORMALIZER_ADVISORY_LOCK_ID},
    )
    db.commit()


def _normalize_status(value: str | None) -> str | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    if any(token in text_value for token in ("신청가능", "접수중", "상시")):
        return "open"
    if any(token in text_value for token in ("마감", "종료")):
        return "closed"
    if "공고" in text_value or "안내" in text_value:
        return "notice"
    return text_value


def _status_from_deadline(deadline: str | None) -> str | None:
    text_value = _clean_text(deadline)
    if not text_value:
        return None
    if "상시" in text_value:
        return "open"
    if any(token in text_value for token in ("마감", "종료")):
        return "closed"
    return "notice"


def _parse_datetime(value: str | None) -> datetime | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    text_value = text_value.replace("/", "-")
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y.%m.%d %H:%M", "%Y.%m.%d"):
        try:
            if pattern in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M"):
                match = re.search(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}\s+\d{1,2}:\d{2}", text_value)
            else:
                match = re.search(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}", text_value)
            if match:
                return datetime.strptime(match.group(0), pattern)
        except ValueError:
            pass
    return None


def _parse_deadline_range(value: str | None) -> tuple[datetime | None, datetime | None]:
    text_value = _clean_text(value)
    if not text_value:
        return None, None
    matches = re.findall(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", text_value)
    dates: list[datetime] = []
    for year, month, day in matches[:2]:
        try:
            dates.append(datetime(int(year), int(month), int(day)))
        except ValueError:
            continue
    if not dates:
        return None, None
    if len(dates) == 1:
        return None, dates[0]
    return dates[0], dates[1]


def _split_requirement_lines(value: str | None) -> list[str]:
    text_value = _clean_text(value)
    if not text_value:
        return []
    lines = re.split(r"(?:\r?\n|○|ㆍ|•|\(\w+\)|\d+\.)", text_value)
    return [
        cleaned
        for line in lines
        if (cleaned := _clean_text(line))
    ]


def _business_tags_from_text(value: str) -> list[str]:
    tags = []
    if "소상공인" in value:
        tags.append("small_business")
    if "예비" in value or "창업" in value:
        tags.append("pre_founder")
    return tags


def _duplicate_group_key(title: str | None, organization: str | None) -> str:
    return _make_hash(
        {
            "title": re.sub(r"\s+", "", (title or "").lower()),
            "organization": re.sub(r"\s+", "", (organization or "").lower()),
        }
    )


def _stable_short_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _make_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _summarize(value: str | None, limit: int = 180) -> str | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    sentence = re.split(r"(?<=[.!?。])\s+", text_value)[0]
    return sentence[:limit]


def _join_sections(sections: list[tuple[str, str | None]]) -> str | None:
    parts = []
    for title, value in sections:
        text_value = _clean_text(value)
        if text_value:
            parts.append(f"[{title}]\n{text_value}")
    return "\n\n".join(parts) or None


def _join_text(values: list[str | None]) -> str | None:
    return "\n".join(value for value in (_clean_text(item) for item in values) if value) or None


def _first_text(*values: str | None) -> str | None:
    for value in values:
        text_value = _clean_text(value)
        if text_value:
            return text_value
    return None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = re.sub(r"\s+", " ", value).strip()
    return text_value or None


def _compact_list(values: list[str | None]) -> list[str]:
    return [value for value in (_clean_text(item) for item in values) if value]


def _dedupe_dicts(values: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    seen = set()
    output = []
    for value in values:
        marker = value.get(key)
        if not marker or marker in seen:
            continue
        seen.add(marker)
        output.append(value)
    return output


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
