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
    ensure_normalized_policy_schema,
)
from app.models.policy import PolicyAnnouncement, PolicyAttachment, PolicyProgramPage


SECTION_TYPE_BY_TITLE = {
    "사업목적": "summary",
    "서비스 목적": "summary",
    "지원규모": "support_content",
    "지원내용": "support_content",
    "지원 내용": "support_content",
    "지원대상": "eligibility",
    "지원 대상": "eligibility",
    "선정기준": "eligibility",
    "선정 기준": "eligibility",
    "대상": "eligibility",
    "신청기간": "application",
    "신청 기간": "application",
    "신청기한": "deadline",
    "신청 기한": "deadline",
    "신청방법": "application",
    "신청 방법": "application",
    "신청·접수": "application",
    "신청‧접수": "application",
    "접수방법": "application",
    "접수 방법": "application",
    "지원절차": "procedure",
    "지원 절차": "procedure",
    "추진절차": "procedure",
    "추진 절차": "procedure",
    "구비서류": "requirements",
    "구비 서류": "requirements",
    "신청서류": "requirements",
    "신청 서류": "requirements",
    "제출서류": "requirements",
    "제출 서류": "requirements",
    "제출자료": "requirements",
    "제출 자료": "requirements",
    "증빙서류": "requirements",
    "증빙 서류": "requirements",
    "필요서류": "requirements",
    "필요 서류": "requirements",
    "문의처": "contact",
    "전화문의": "contact",
    "접수기관": "application",
    "사업명": "summary",
}

SECTION_TITLE_ALIASES = {
    "신청ㆍ접수": "신청·접수",
    "신청·접수": "신청·접수",
    "신청‧접수": "신청·접수",
    "신청 접수": "신청·접수",
    "자세한 사항은 여기로 문의하세요": "문의처",
    "자세한 사항은 여기로 문의하시기 바랍니다": "문의처",
    "자세한 사항은 아래 문의처로 연락바랍니다": "문의처",
}

SIDO_ALIASES = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "대구": "대구광역시",
    "대구광역시": "대구광역시",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "광주": "광주광역시",
    "광주광역시": "광주광역시",
    "대전": "대전광역시",
    "대전광역시": "대전광역시",
    "울산": "울산광역시",
    "울산광역시": "울산광역시",
    "세종": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}

REGION_GROUPS = {
    "수도권": ["서울특별시", "인천광역시", "경기도"],
    "충청권": ["대전광역시", "세종특별자치시", "충청북도", "충청남도"],
    "충청호남권": ["대전광역시", "세종특별자치시", "충청북도", "충청남도", "광주광역시", "전북특별자치도", "전라남도"],
    "호남권": ["광주광역시", "전북특별자치도", "전라남도"],
    "영남권": ["부산광역시", "대구광역시", "울산광역시", "경상북도", "경상남도"],
    "동남권": ["부산광역시", "울산광역시", "경상남도"],
    "대경권": ["대구광역시", "경상북도"],
    "강원권": ["강원특별자치도"],
    "제주권": ["제주특별자치도"],
}

INDUSTRY_KEYWORDS = {
    "restaurant": ("음식", "외식", "식당", "요식", "식품", "카페", "베이커리"),
    "manufacturing": ("제조", "소공인", "공장", "생산", "스마트제조"),
    "retail": ("유통", "도소매", "판매", "슈퍼", "상점", "가맹점"),
    "tourism": ("관광", "숙박", "호텔", "여행"),
    "market": ("전통시장", "상점가", "골목상권", "상권"),
    "export": ("수출", "해외", "글로벌", "FTA"),
    "digital": ("디지털", "스마트", "온라인", "소프트웨어", "AI"),
    "agriculture_fishery_forestry": ("농업", "어업", "수산", "임업", "축산"),
    "information_communication": ("정보통신", "ICT", "IT"),
}

BUSINESS_STATUS_KEYWORDS = {
    "small_business": ("소상공인", "소기업", "영세"),
    "small_manufacturer": ("소공인", "도시형소공인"),
    "pre_founder": ("예비창업", "예비 창업", "창업예정", "창업 예정", "예비창업자"),
    "operating_business": ("기존사업자", "사업자", "영업중", "정상영업", "운영 중", "운영중"),
    "closing_business": ("폐업", "폐업예정", "폐업 예정", "재기", "희망리턴"),
    "traditional_market": ("전통시장", "상인회", "상점가"),
}


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

        ensure_normalized_policy_schema(db)
        db.commit()

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
        .all()
    )

    for row in rows:
        sections = _sections_from_sbiz24_text(row.content_text)
        metadata = _source_metadata(
            source="sbiz24",
            title=row.title,
            category=row.category,
            target_text=row.target,
            content_text=row.content_text,
            sections=sections,
            region_text=_join_text(
                [
                    row.title,
                    row.organization,
                    row.target,
                    _first_section_text_by_type(sections, "eligibility"),
                ]
            ),
        )
        target_text = _first_text(metadata["target_text"], row.target)
        support_content = _first_text(metadata["support_content_text"], row.content_text)
        docs = _sbiz24_documents(row, sections, metadata)
        filter_columns = _filter_columns_from_metadata(metadata)
        payload = {
            "source": "sbiz24",
            "source_pk": str(row.pbanc_sn),
            "canonical_key": f"sbiz24:{row.pbanc_sn}",
            "duplicate_group_key": _duplicate_group_key(row.title, row.organization),
            "title": row.title,
            "summary": _first_text(metadata["summary_text"], _summarize(support_content), row.title),
            "body": row.content_text,
            "organization": row.organization,
            "support_type": row.category,
            "target_text": target_text,
            "support_content": support_content,
            "region_scope": metadata["region"]["region_scope"],
            "sido": metadata["region"]["sido"],
            "sigungu": metadata["region"]["sigungu"],
            **filter_columns,
            "status": _normalize_status(row.status),
            "apply_start": _parse_datetime(row.apply_start),
            "apply_end": _parse_datetime(row.apply_end, end_of_day=True),
            "apply_url": row.detail_url,
            "industry_tags": metadata["industry_tags"],
            "business_status_tags": _merge_unique_lists(_business_tags_from_text(row.target or ""), metadata["business_status_tags"]),
            "eligibility": {
                "source": "sbiz24",
                "target": row.target,
                "category": row.category,
                "status_raw": row.status,
                "apply_start_raw": row.apply_start,
                "apply_end_raw": row.apply_end,
                "region": metadata["region"],
                "business_status_tags": metadata["business_status_tags"],
                "industry_tags": metadata["industry_tags"],
                "employee_limit": metadata["employee_limit"],
                "sales_limit": metadata["sales_limit"],
                "business_age_limit": metadata["business_age_limit"],
                "money_conditions": metadata["money_conditions"],
                "application_methods": metadata["application_methods"],
                "contacts": metadata["contacts"],
                "extraction_method": "rule",
            },
            "required_documents": metadata["required_documents"],
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
        .all()
    )

    for row in rows:
        source_pk = _stable_short_key(row.source_url)
        sections = _sections_from_semas(row)
        metadata = _source_metadata(
            source="semas",
            title=row.program_name,
            category=row.category,
            target_text=None,
            content_text=row.content_text,
            sections=sections,
            extra_texts=row.raw_breadcrumbs_json or [],
            default_business_status_tags=["small_business"],
            region_text=_join_text(
                [
                    row.program_name,
                    *[_as_text(item) for item in (row.raw_breadcrumbs_json or [])],
                    _first_section_text_by_type(sections, "eligibility"),
                ]
            ),
        )
        target_text = metadata["target_text"]
        support_content = _first_text(metadata["support_content_text"], row.content_text)
        docs = _semas_documents(row, sections, metadata)
        filter_columns = _filter_columns_from_metadata(metadata)
        payload = {
            "source": "semas",
            "source_pk": source_pk,
            "canonical_key": f"semas:{source_pk}",
            "duplicate_group_key": _duplicate_group_key(row.program_name, "소상공인시장진흥공단"),
            "title": row.program_name,
            "summary": _first_text(metadata["summary_text"], _summarize(support_content), row.program_name),
            "body": row.content_text,
            "organization": "소상공인시장진흥공단",
            "support_type": row.category,
            "target_text": target_text,
            "support_content": support_content,
            "region_scope": metadata["region"]["region_scope"],
            "sido": metadata["region"]["sido"],
            "sigungu": metadata["region"]["sigungu"],
            **filter_columns,
            "status": "notice",
            "apply_start": None,
            "apply_end": None,
            "apply_url": row.source_url,
            "industry_tags": metadata["industry_tags"],
            "business_status_tags": metadata["business_status_tags"],
            "eligibility": {
                "source": "semas",
                "source_url": row.source_url,
                "category": row.category,
                "breadcrumbs": row.raw_breadcrumbs_json or [],
                "region": metadata["region"],
                "business_status_tags": metadata["business_status_tags"],
                "industry_tags": metadata["industry_tags"],
                "employee_limit": metadata["employee_limit"],
                "sales_limit": metadata["sales_limit"],
                "business_age_limit": metadata["business_age_limit"],
                "money_conditions": metadata["money_conditions"],
                "application_methods": metadata["application_methods"],
                "contacts": metadata["contacts"],
                "extraction_method": "rule",
            },
            "required_documents": metadata["required_documents"],
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
        application_method = _first_text(detail.application_method if detail else None, list_row.application_method)
        contacts = _extract_contacts(
            _join_text([detail.contact if detail else None, list_row.contact_phone])
        )
        gov_text_blob = _join_text(
            [
                list_row.service_name,
                list_row.service_field,
                list_row.support_type,
                target_text,
                support_content,
                _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                application_method,
            ]
        )
        gov_eligibility_blob = _join_text(
            [
                list_row.service_name,
                list_row.service_field,
                list_row.support_type,
                target_text,
                _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
            ]
        )
        region = _extract_region_metadata(
            _join_text(
                [
                    list_row.service_name,
                    list_row.organization_name,
                    detail.organization_name if detail else None,
                    target_text,
                    _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                ]
            ),
            default_scope="national",
        )
        docs = _gov24_documents(
            body=body,
            target_text=target_text,
            support_content=support_content,
            required_docs=docs_required,
            application_method=application_method,
            application_deadline=application_deadline,
            selection_criteria=_first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
            contact=_first_text(detail.contact if detail else None, list_row.contact_phone),
            reception_institution=_first_text(detail.reception_institution_name if detail else None, list_row.reception_institution),
            laws=detail.laws if detail else None,
        )
        gov_metadata = {
            "region": region,
            "required_documents": docs_required,
            "application_methods": _extract_application_methods(application_method),
            "contacts": contacts,
            "employee_limit": _extract_employee_limit(gov_eligibility_blob),
            "sales_limit": _extract_sales_limit(gov_eligibility_blob),
            "business_age_limit": _extract_business_age_limit(gov_eligibility_blob),
        }
        filter_columns = _filter_columns_from_metadata(gov_metadata)
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
            "region_scope": region["region_scope"],
            "sido": region["sido"],
            "sigungu": region["sigungu"],
            **filter_columns,
            "status": _status_from_deadline(application_deadline, apply_start, apply_end),
            "apply_start": apply_start,
            "apply_end": apply_end,
            "apply_url": _first_text(detail.online_application_url if detail else None, list_row.detail_url),
            "industry_tags": _merge_unique_lists(
                condition_payload["industry_tags"],
                _tags_from_keyword_map(gov_eligibility_blob, INDUSTRY_KEYWORDS),
            ),
            "business_status_tags": _merge_unique_lists(
                condition_payload["business_status_tags"],
                _tags_from_keyword_map(gov_eligibility_blob, BUSINESS_STATUS_KEYWORDS),
            ),
            "eligibility": {
                "source": "gov24",
                "user_type": list_row.user_type,
                "service_field": list_row.service_field,
                "selection_criteria": _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                "application_deadline": application_deadline,
                "application_methods": filter_columns["application_methods"],
                "contacts": filter_columns["contact_points"],
                "region": region,
                "employee_limit": gov_metadata["employee_limit"],
                "sales_limit": gov_metadata["sales_limit"],
                "business_age_limit": gov_metadata["business_age_limit"],
                "money_conditions": _extract_money_conditions(gov_text_blob),
                "support_conditions": condition_payload["raw_flags"],
                "support_condition_labels": condition_payload["condition_labels"],
                "age": condition_payload["age"],
                "income_ranges": condition_payload["income_ranges"],
                "target_traits": condition_payload["target_traits"],
                "extraction_method": "gov24_detail_and_condition_codes",
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
    created = 0
    existing = {
        (document.document_type, document.text_hash): document
        for document in policy.documents
    }
    desired_keys: set[tuple[str, str]] = set()
    for document in documents:
        text_value = _clean_text(document.get("text"))
        if not text_value:
            continue
        document_type = document.get("document_type") or "body"
        text_hash = _make_hash(text_value)
        key = (document_type, text_hash)
        if key in desired_keys:
            continue
        desired_keys.add(key)
        existing_document = existing.get(key)
        if existing_document is not None:
            existing_document.source_ref = document.get("source_ref")
            existing_document.title = document.get("title")
            existing_document.text = text_value
            continue
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

    for key, document in existing.items():
        if key not in desired_keys:
            db.delete(document)

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


def _sbiz24_documents(
    row: PolicyAnnouncement,
    sections: list[dict[str, str | None]],
    metadata: dict[str, Any],
) -> list[dict[str, str | None]]:
    documents = [
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
    if row.target:
        documents.append(
            {
                "document_type": "eligibility",
                "source_ref": f"policy_announcements:{row.pbanc_sn}:target",
                "title": "지원 대상",
                "text": row.target,
            }
        )
    documents.extend(
        _documents_from_sections(
            source_ref_prefix=f"policy_announcements:{row.pbanc_sn}",
            sections=sections,
        )
    )
    documents.extend(_metadata_documents(f"policy_announcements:{row.pbanc_sn}", metadata))
    return documents


def _semas_documents(
    row: PolicyProgramPage,
    sections: list[dict[str, str | None]],
    metadata: dict[str, Any],
) -> list[dict[str, str | None]]:
    documents = [
        {
            "document_type": "body",
            "source_ref": f"policy_program_pages:{row.id}:content_text",
            "title": row.program_name,
            "text": row.content_text,
        }
    ]
    documents.extend(
        _documents_from_sections(
            source_ref_prefix=f"policy_program_pages:{row.id}",
            sections=sections,
        )
    )
    documents.extend(_metadata_documents(f"policy_program_pages:{row.id}", metadata))
    return documents


def _gov24_documents(
    *,
    body: str | None,
    target_text: str | None,
    support_content: str | None,
    required_docs: list[dict[str, str]],
    application_method: str | None,
    application_deadline: str | None,
    selection_criteria: str | None,
    contact: str | None,
    reception_institution: str | None,
    laws: str | None,
) -> list[dict[str, str | None]]:
    requirement_text = "\n".join(doc["name"] for doc in required_docs)
    return [
        {"document_type": "body", "source_ref": "gov24:body", "title": "정책 본문", "text": body},
        {"document_type": "eligibility", "source_ref": "gov24:support_target", "title": "지원 대상", "text": target_text},
        {"document_type": "eligibility", "source_ref": "gov24:selection_criteria", "title": "선정 기준", "text": selection_criteria},
        {"document_type": "requirements", "source_ref": "gov24:required_docs", "title": "구비 서류", "text": requirement_text},
        {"document_type": "application", "source_ref": "gov24:application_method", "title": "신청 방법", "text": application_method},
        {"document_type": "deadline", "source_ref": "gov24:application_deadline", "title": "신청 기한", "text": application_deadline},
        {"document_type": "contact", "source_ref": "gov24:contact", "title": "문의처", "text": contact},
        {"document_type": "application", "source_ref": "gov24:reception_institution", "title": "접수 기관", "text": reception_institution},
        {"document_type": "reference", "source_ref": "gov24:laws", "title": "관련 법령", "text": laws},
        {"document_type": "support_content", "source_ref": "gov24:support_content", "title": "지원 내용", "text": support_content},
    ]


def _sections_from_sbiz24_text(value: str | None) -> list[dict[str, str | None]]:
    text_value = _clean_text(value)
    if not text_value:
        return []

    titles = sorted(
        set(SECTION_TYPE_BY_TITLE) | set(SECTION_TITLE_ALIASES),
        key=len,
        reverse=True,
    )
    title_pattern = "|".join(re.escape(title) for title in titles)
    pattern = re.compile(
        rf"(?:^|\s)(?:[□■◆◇○ㅇ※\-*ㆍ·•]*\s*)({title_pattern})\s*(?:[:：※]|(?=\s))"
    )
    matches = list(pattern.finditer(text_value))
    sections: list[dict[str, str | None]] = []
    for index, match in enumerate(matches):
        title = _normalize_section_title(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text_value)
        section_text = _clean_text(text_value[start:end].strip(" :-：※"))
        if not section_text or len(section_text) < 4:
            continue
        sections.append(
            {
                "title": title,
                "text": section_text,
                "document_type": _document_type_for_title(title),
            }
        )
    return _dedupe_sections(sections)


def _sections_from_semas(row: PolicyProgramPage) -> list[dict[str, str | None]]:
    sections: list[dict[str, str | None]] = []
    for section in row.sections_json or []:
        if not isinstance(section, dict):
            continue
        title = _normalize_section_title(_as_text(section.get("title")))
        text_value = _clean_text(_as_text(section.get("body") or section.get("text")))
        if not text_value:
            continue
        sections.append(
            {
                "title": title or row.program_name,
                "text": text_value,
                "document_type": _document_type_for_title(title),
            }
        )
    return _dedupe_sections(sections)


def _source_metadata(
    *,
    source: str,
    title: str | None,
    category: str | None,
    target_text: str | None,
    content_text: str | None,
    sections: list[dict[str, str | None]],
    extra_texts: list[Any] | None = None,
    default_business_status_tags: list[str] | None = None,
    region_text: str | None = None,
) -> dict[str, Any]:
    text_blob = _join_text(
        [
            title,
            category,
            target_text,
            content_text,
            *[_as_text(item) for item in (extra_texts or [])],
            *[section.get("title") for section in sections],
            *[section.get("text") for section in sections],
        ]
    ) or ""
    eligibility_text = _join_text(
        [
            title,
            category,
            target_text,
            _first_section_text_by_type(sections, "eligibility"),
        ]
    ) or text_blob

    business_status_tags = _merge_unique_lists(
        default_business_status_tags or [],
        _tags_from_keyword_map(eligibility_text, BUSINESS_STATUS_KEYWORDS),
    )
    industry_tags = _tags_from_keyword_map(eligibility_text, INDUSTRY_KEYWORDS)
    required_documents = _extract_required_documents(sections, source)
    application_text = _join_text(
        [
            _first_section_text_by_type(sections, "application"),
            _first_section_text_by_type(sections, "deadline"),
        ]
    )
    contacts_text = _first_section_text_by_type(sections, "contact")

    return {
        "region": _extract_region_metadata(region_text if region_text is not None else eligibility_text),
        "summary_text": _first_section_text_by_type(sections, "summary"),
        "target_text": _first_text(_first_section_text_by_type(sections, "eligibility"), target_text),
        "support_content_text": _first_section_text_by_type(sections, "support_content"),
        "required_documents": required_documents,
        "business_status_tags": business_status_tags,
        "industry_tags": industry_tags,
        "employee_limit": _extract_employee_limit(eligibility_text),
        "sales_limit": _extract_sales_limit(eligibility_text),
        "business_age_limit": _extract_business_age_limit(eligibility_text),
        "money_conditions": _extract_money_conditions(text_blob),
        "application_methods": _extract_application_methods(application_text or text_blob),
        "contacts": _extract_contacts(_join_text([contacts_text, text_blob])),
    }


def _filter_columns_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    region = metadata.get("region") or {}
    required_documents = metadata.get("required_documents") or []
    employee_limit = metadata.get("employee_limit") or {}
    sales_limit = metadata.get("sales_limit") or {}
    business_age_limit = metadata.get("business_age_limit") or {}
    return {
        "matched_sidos": region.get("matched_sidos") or [],
        "region_confidence": region.get("confidence"),
        "application_methods": metadata.get("application_methods") or [],
        "contact_points": metadata.get("contacts") or [],
        "employee_limit_value": employee_limit.get("value"),
        "employee_limit_operator": employee_limit.get("operator"),
        "sales_limit_amount_krw": sales_limit.get("amount_krw"),
        "sales_limit_operator": sales_limit.get("operator"),
        "business_age_limit_value": business_age_limit.get("value"),
        "business_age_limit_operator": business_age_limit.get("operator"),
        "required_document_count": len(required_documents),
        "has_required_documents": bool(required_documents),
    }


def _documents_from_sections(
    *,
    source_ref_prefix: str,
    sections: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    documents: list[dict[str, str | None]] = []
    for index, section in enumerate(sections):
        text_value = _clean_text(section.get("text"))
        if not text_value:
            continue
        title = _normalize_section_title(section.get("title"))
        documents.append(
            {
                "document_type": section.get("document_type") or _document_type_for_title(title),
                "source_ref": f"{source_ref_prefix}:sections:{index}",
                "title": title,
                "text": text_value,
            }
        )
    return documents


def _metadata_documents(source_ref_prefix: str, metadata: dict[str, Any]) -> list[dict[str, str | None]]:
    documents: list[dict[str, str | None]] = []
    required_documents = metadata.get("required_documents") or []
    if required_documents:
        documents.append(
            {
                "document_type": "requirements",
                "source_ref": f"{source_ref_prefix}:metadata:required_documents",
                "title": "필수 제출 서류",
                "text": "\n".join(doc["name"] for doc in required_documents if doc.get("name")),
            }
        )
    contacts = metadata.get("contacts") or []
    if contacts:
        documents.append(
            {
                "document_type": "contact",
                "source_ref": f"{source_ref_prefix}:metadata:contacts",
                "title": "문의처",
                "text": "\n".join(contacts),
            }
        )
    employee_limit = metadata.get("employee_limit")
    sales_limit = metadata.get("sales_limit")
    business_age_limit = metadata.get("business_age_limit")
    if employee_limit or sales_limit or business_age_limit:
        documents.append(
            {
                "document_type": "eligibility",
                "source_ref": f"{source_ref_prefix}:metadata:eligibility_rules",
                "title": "구조화 자격 조건",
                "text": json.dumps(
                    {
                        "employee_limit": employee_limit,
                        "sales_limit": sales_limit,
                        "business_age_limit": business_age_limit,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return documents


def _normalize_section_title(value: str | None) -> str | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    text_value = text_value.strip("[](){}<>:：※ㆍ·•- ")
    text_value = re.sub(r"\s+", " ", text_value)
    return SECTION_TITLE_ALIASES.get(text_value, text_value)


def _document_type_for_title(value: str | None) -> str:
    title = _normalize_section_title(value)
    if not title:
        return "section"
    compact_title = re.sub(r"\s+", "", title)
    for key, document_type in SECTION_TYPE_BY_TITLE.items():
        if re.sub(r"\s+", "", key) in compact_title:
            return document_type
    if "서류" in compact_title:
        return "requirements"
    if "문의" in compact_title or "연락" in compact_title:
        return "contact"
    if "신청" in compact_title or "접수" in compact_title:
        return "application"
    if "대상" in compact_title or "자격" in compact_title or "조건" in compact_title:
        return "eligibility"
    if "내용" in compact_title or "규모" in compact_title:
        return "support_content"
    return "section"


def _first_section_text_by_type(
    sections: list[dict[str, str | None]],
    document_type: str,
) -> str | None:
    values = [
        section.get("text")
        for section in sections
        if (section.get("document_type") or _document_type_for_title(section.get("title"))) == document_type
    ]
    return _join_text(values)


def _extract_region_metadata(value: str | None, default_scope: str = "unknown") -> dict[str, Any]:
    text_value = _clean_text(value) or ""
    matched_sidos: list[str] = []
    for alias, sido in sorted(SIDO_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if _contains_region_alias(text_value, alias) and sido not in matched_sidos:
            matched_sidos.append(sido)
    for group_name, sidos in REGION_GROUPS.items():
        if group_name not in text_value:
            continue
        for sido in sidos:
            if sido not in matched_sidos:
                matched_sidos.append(sido)

    is_national = any(token in text_value for token in ("전국", "전 지역", "전국민", "전국 단위"))
    if matched_sidos:
        region_scope = "local"
        confidence = 0.8
    elif is_national:
        region_scope = "national"
        confidence = 0.75
    else:
        region_scope = default_scope
        confidence = 0.5 if default_scope != "unknown" else 0.2

    sigungu = _extract_sigungu_after_sido(text_value, matched_sidos) if matched_sidos else None

    return {
        "region_scope": region_scope,
        "sido": matched_sidos[0] if matched_sidos else None,
        "sigungu": sigungu,
        "matched_sidos": matched_sidos,
        "confidence": confidence,
        "extraction_method": "rule",
    }


def _contains_region_alias(text_value: str, alias: str) -> bool:
    if len(alias) >= 4 or alias.endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도")):
        return alias in text_value
    return bool(re.search(rf"(?<![가-힣]){re.escape(alias)}(?:시|도)?(?![가-힣])", text_value))


def _extract_required_documents(
    sections: list[dict[str, str | None]],
    source: str,
) -> list[dict[str, Any]]:
    candidate_texts = [
        section.get("text")
        for section in sections
        if (section.get("document_type") or _document_type_for_title(section.get("title"))) == "requirements"
    ]

    values: list[dict[str, Any]] = []
    for candidate in candidate_texts:
        for line in _split_requirement_lines(candidate):
            for name in _split_document_names(line):
                if _is_weak_document_name(name):
                    continue
                values.append(
                    {
                        "name": name,
                        "description": "",
                        "source": source,
                        "confidence": 0.7,
                        "extraction_method": "rule",
                    }
                )
    return _dedupe_dicts(values, "name")


def _extract_sigungu_after_sido(text_value: str, matched_sidos: list[str]) -> str | None:
    aliases = [
        alias
        for alias, sido in SIDO_ALIASES.items()
        if sido in matched_sidos
    ]
    bad_tokens = (
        "시군구",
        "시도",
        "소상공인시",
        "소상공인시장",
        "중소기업",
        "고용시",
        "산업구",
        "전시",
    )
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = re.compile(rf"{re.escape(alias)}\s+([가-힣]{{2,6}}(?:시|군|구))")
        match = pattern.search(text_value)
        if not match:
            continue
        token = match.group(1)
        if token in SIDO_ALIASES.values() or any(bad in token for bad in bad_tokens):
            continue
        return token
    return None


def _split_document_names(value: str) -> list[str]:
    text_value = _clean_text(value)
    if not text_value:
        return []
    parts = re.split(r"\s*(?:,|，|/| 및 | 또는 |ㆍ|·|•)\s*", text_value)
    return [part for part in (_clean_text(item) for item in parts) if part]


def _is_weak_document_name(value: str) -> bool:
    text_value = _clean_text(value) or ""
    if len(text_value) < 2 or len(text_value) > 120:
        return True
    weak_tokens = (
        "자세한",
        "첨부파일",
        "공고문",
        "참고",
        "확인",
        "세부내용",
        "문의처",
        "홈페이지",
        "담당자",
        "제출서류와 함께",
        "제출서류 양식",
        "신청서류 검토",
        "소상공인24 통해",
        "온라인 접수",
        "해당없음",
        "해당 없음",
        "없음",
        "사업별 공고",
    )
    if any(token in text_value for token in weak_tokens):
        return True
    strong_tokens = ("신청서", "동의서", "사업자", "증명", "확인서", "계획서", "등록증", "신고서", "자료", "서류")
    return not any(token in text_value for token in strong_tokens)


def _extract_employee_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    patterns = [
        r"((?:상시\s*)?근로자\s*수?[^0-9]{0,12}(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과))",
        r"((\d+)\s*(?:명|인)\s*(미만|이하|이상|초과)[^.\n]{0,20}(?:근로자|사업장|업체))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        return {
            "value": int(match.group(2)),
            "operator": _operator_symbol(match.group(3)),
            "unit": "people",
            "source_text": match.group(1),
            "extraction_method": "rule",
        }
    return None


def _extract_sales_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    pattern = re.compile(
        r"((?:연\s*)?(?:전년도\s*)?(?:매출액?|연매출)[^0-9]{0,25}"
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
        r"\s*(미만|이하|이상|초과)?)"
    )
    match = pattern.search(text_value)
    if not match:
        return None
    return {
        "amount_krw": _money_to_krw(match.group(2), match.group(3)),
        "operator": _operator_symbol(match.group(4) or "이하"),
        "source_text": match.group(1),
        "extraction_method": "rule",
    }


def _extract_business_age_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    patterns = [
        r"((?:창업|업력)[^0-9]{0,10}(\d+)\s*년\s*(이내|이하|미만|초과|경과하지\s*(?:않은|아니한)))",
        r"((\d+)\s*년\s*(이내|이하|미만|초과|경과하지\s*(?:않은|아니한))[^.\n]{0,20}(?:창업|업력))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        limit_years = int(match.group(2))
        op_text = match.group(3)
        operator = _operator_symbol(op_text)
        if op_text == "이내" or "경과하지" in op_text:
            operator = "<="
        return {
            "value": limit_years,
            "operator": operator,
            "unit": "years",
            "source_text": match.group(1),
            "extraction_method": "rule",
        }
    return None


def _extract_money_conditions(value: str | None) -> list[dict[str, Any]]:
    text_value = _clean_text(value)
    if not text_value:
        return []
    pattern = re.compile(
        r"(.{0,24}?)(\d+(?:,\d{3})*(?:\.\d+)?)\s*"
        r"(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
        r"\s*(미만|이하|이상|초과|한도|내외|까지)?"
    )
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in pattern.finditer(text_value):
        context = _clean_text(match.group(1)) or ""
        source_text = _clean_text("".join(part or "" for part in match.groups())) or ""
        if source_text in seen:
            continue
        seen.add(source_text)
        values.append(
            {
                "kind": _money_condition_kind(context),
                "amount_krw": _money_to_krw(match.group(2), match.group(3)),
                "operator": _operator_symbol(match.group(4) or "이하"),
                "source_text": source_text,
            }
        )
        if len(values) >= 10:
            break
    return values


def _extract_application_methods(value: str | None) -> list[str]:
    text_value = _clean_text(value) or ""
    method_map = {
        "online": ("온라인", "홈페이지", "사이트", "전자신청", "인터넷", "플랫폼", "앱"),
        "visit": ("방문", "내방", "현장"),
        "mail": ("우편", "등기"),
        "fax": ("팩스", "FAX", "fax"),
        "email": ("이메일", "메일", "전자우편"),
        "e_document": ("전자문서", "공문", "온나라"),
    }
    return [method for method, tokens in method_map.items() if any(token in text_value for token in tokens)]


def _extract_contacts(value: str | None) -> list[str]:
    text_value = _clean_text(value) or ""
    contacts = re.findall(r"\b\d{2,4}-\d{3,4}-\d{4}\b|\b1[3568]\d{2}-\d{4}\b|\b1357\b", text_value)
    return _merge_unique_lists([], contacts)


def _tags_from_keyword_map(value: str | None, keyword_map: dict[str, tuple[str, ...]]) -> list[str]:
    text_value = _clean_text(value) or ""
    return [tag for tag, keywords in keyword_map.items() if any(keyword in text_value for keyword in keywords)]


def _operator_symbol(value: str) -> str:
    return {
        "미만": "<",
        "이하": "<=",
        "초과": ">",
        "이상": ">=",
        "한도": "<=",
        "까지": "<=",
        "내외": "~",
    }.get(value, "<=")


def _money_to_krw(number_text: str, unit: str) -> int:
    number = float(number_text.replace(",", ""))
    compact_unit = re.sub(r"\s+", "", unit)
    if compact_unit == "억원":
        multiplier = 100_000_000
    elif compact_unit == "천만원":
        multiplier = 10_000_000
    elif compact_unit == "백만원":
        multiplier = 1_000_000
    elif compact_unit == "만원":
        multiplier = 10_000
    else:
        multiplier = 1
    return int(number * multiplier)


def _money_condition_kind(context: str) -> str:
    if "매출" in context:
        return "sales"
    if "보수" in context or "소득" in context:
        return "income"
    if "지원" in context or "한도" in context or "자금" in context:
        return "support_amount"
    if "부담" in context:
        return "self_payment"
    return "amount"


def _dedupe_sections(sections: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    seen: set[tuple[str | None, str | None]] = set()
    output = []
    for section in sections:
        key = (section.get("title"), section.get("text"))
        if key in seen:
            continue
        seen.add(key)
        output.append(section)
    return output


def _required_documents_from_gov24(detail: Gov24ServiceDetail | None) -> list[dict[str, Any]]:
    if detail is None:
        return []
    values = []
    for source, text_value in (
        ("required_docs", detail.required_docs),
        ("required_docs_by_official", detail.required_docs_by_official),
        ("identity_required_docs", detail.identity_required_docs),
    ):
        for line in _split_requirement_lines(text_value):
            if line in {"해당없음", "없음", "해당 없음"} or _is_weak_document_name(line):
                continue
            values.append(
                {
                    "name": line,
                    "description": "",
                    "source": source,
                    "confidence": 0.95,
                    "extraction_method": "gov24_detail",
                }
            )
    return _dedupe_dicts(values, "name")


def _condition_payload(condition: Gov24SupportCondition | None) -> dict[str, Any]:
    if condition is None:
        return {
            "industry_tags": [],
            "business_status_tags": [],
            "raw_flags": {},
            "condition_labels": [],
            "age": {},
            "income_ranges": [],
            "target_traits": [],
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
    trait_map = {
        "ja0101_male": "male",
        "ja0102_female": "female",
        "ja0301_pre_parent_infertility": "pre_parent_infertility",
        "ja0302_pregnant": "pregnant",
        "ja0303_childbirth_adoption": "childbirth_adoption",
        "ja0313_farmer": "farmer",
        "ja0314_fisher": "fisher",
        "ja0315_livestock_farmer": "livestock_farmer",
        "ja0316_forester": "forester",
        "ja0317_elementary_student": "elementary_student",
        "ja0318_middle_school_student": "middle_school_student",
        "ja0319_high_school_student": "high_school_student",
        "ja0320_college_student": "college_student",
        "ja0322_no_personal_trait": "no_personal_trait",
        "ja0326_worker": "worker",
        "ja0327_job_seeker": "job_seeker",
        "ja0328_disabled": "disabled",
        "ja0329_veteran": "veteran",
        "ja0330_disease_patient": "disease_patient",
        "ja0401_multicultural_family": "multicultural_family",
        "ja0402_north_korean_defector": "north_korean_defector",
        "ja0403_single_parent_grandparent_family": "single_parent_grandparent_family",
        "ja0404_single_person_household": "single_person_household",
        "ja0410_no_household_trait": "no_household_trait",
        "ja0411_multi_child_family": "multi_child_family",
        "ja0412_homeless_household": "homeless_household",
        "ja0413_new_resident": "new_resident",
        "ja0414_extended_family": "extended_family",
        "ja2102_social_welfare_facility": "social_welfare_facility",
        "ja2103_institution_group": "institution_group",
        "ja2201_company_manufacturing": "company_manufacturing",
    }
    income_map = {
        "ja0201_income_0_50": "0_50",
        "ja0202_income_51_75": "51_75",
        "ja0203_income_76_100": "76_100",
        "ja0204_income_101_200": "101_200",
        "ja0205_income_over_200": "over_200",
    }
    mapped_columns = set(industry_map) | set(status_map) | set(trait_map) | set(income_map) | {
        "ja0110_age_start",
        "ja0111_age_end",
    }
    raw_flags = {
        column: getattr(condition, column)
        for column in mapped_columns
        if getattr(condition, column)
    }
    age = {
        "start": _as_int_text(condition.ja0110_age_start),
        "end": _as_int_text(condition.ja0111_age_end),
    }
    age = {key: value for key, value in age.items() if value is not None}
    condition_labels = []
    for mapping in (industry_map, status_map, trait_map):
        condition_labels.extend(label for column, label in mapping.items() if getattr(condition, column))
    return {
        "industry_tags": [label for column, label in industry_map.items() if getattr(condition, column)],
        "business_status_tags": [label for column, label in status_map.items() if getattr(condition, column)],
        "raw_flags": raw_flags,
        "condition_labels": _merge_unique_lists([], condition_labels),
        "age": age,
        "income_ranges": [label for column, label in income_map.items() if getattr(condition, column)],
        "target_traits": [label for column, label in trait_map.items() if getattr(condition, column)],
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


def _status_from_deadline(
    deadline: str | None,
    apply_start: datetime | None = None,
    apply_end: datetime | None = None,
) -> str | None:
    text_value = _clean_text(deadline)
    if not text_value:
        return None
    now = datetime.now()
    if apply_end is not None and now > apply_end:
        return "closed"
    if apply_start is not None and now < apply_start:
        return "notice"
    if apply_start is not None or apply_end is not None:
        return "open"
    if "상시" in text_value or "소진" in text_value or "연중" in text_value:
        return "open"
    if any(token in text_value for token in ("마감", "종료")):
        return "closed"
    return "notice"


def _parse_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
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
                parsed = datetime.strptime(match.group(0), pattern)
                if end_of_day and "%H:%M" not in pattern:
                    return _as_end_of_day(parsed)
                return parsed
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
    if len(dates) == 1:
        first_date = dates[0]
        year = first_date.year
        remaining_text = re.sub(r"20\d{2}[.\-/년\s]+\d{1,2}[.\-/월\s]+\d{1,2}", "", text_value, count=1)
        second_match = re.search(r"(\d{1,2})[.\-/월\s]+(\d{1,2})", remaining_text)
        if second_match:
            try:
                second_date = datetime(year, int(second_match.group(1)), int(second_match.group(2)))
                if first_date <= second_date:
                    return first_date, _as_end_of_day(second_date)
                else:
                    return second_date, _as_end_of_day(first_date)
            except ValueError:
                pass
        if re.search(r"(?:예산|자금|보증규모|한도)?.{0,10}소진\s*(?:시|때|까지)?", remaining_text):
            return first_date, None
        return None, _as_end_of_day(first_date)
    if not dates:
        return None, None
    return dates[0], _as_end_of_day(dates[1])


def _as_end_of_day(value: datetime) -> datetime:
    return value.replace(hour=23, minute=59, second=59, microsecond=999999)


def _split_requirement_lines(value: str | None) -> list[str]:
    if value is None:
        return []
    raw_text = re.sub(r"\r\n?", "\n", value)
    lines = re.split(
        r"(?:\n+|○|ㆍ|•|◦|▪|▶|[-–]\s+|\(\s*[0-9ivxIVXⅰ-ⅹ]+\s*\)|\d+[.)])",
        raw_text,
    )
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


def _as_int_text(value: Any) -> int | None:
    text_value = _clean_text(_as_text(value))
    if not text_value:
        return None
    match = re.search(r"\d+", text_value.replace(",", ""))
    if not match:
        return None
    return int(match.group(0))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = re.sub(r"\s+", " ", value).strip()
    return text_value or None


def _compact_list(values: list[str | None]) -> list[str]:
    return [value for value in (_clean_text(item) for item in values) if value]


def _merge_unique_lists(*values: list[Any]) -> list[Any]:
    seen = set()
    output = []
    for items in values:
        for item in items:
            if item is None or item == "":
                continue
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            output.append(item)
    return output


def _dedupe_dicts(values: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
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
