from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.gov24 import Gov24ServiceDetail, Gov24ServiceList, Gov24SupportCondition
from app.models.normalized_policy import NormalizedPolicy
from app.models.policy import PolicyAnnouncement, PolicyProgramPage
from app.services.normalization.common import (
    _as_text,
    _clean_text,
    _first_text,
    _join_sections,
    _join_text,
    _make_hash,
    _merge_unique_lists,
    _summarize,
)
from app.services.normalization.documents import (
    _first_section_text_by_type,
    _required_documents_from_gov24,
)
from app.services.normalization.field_extractors import (
    _extract_application_methods,
    _extract_business_age_limit,
    _extract_contacts,
    _extract_employee_limit,
    _extract_industry_condition,
    _extract_money_conditions,
    _extract_sales_limit,
    _tags_from_keyword_map,
)
from app.services.normalization.llm_limits import (
    _llm_cache_from_policy,
    _resolve_limits_with_llm_cache,
)
from app.services.normalization.metadata import (
    BUSINESS_STATUS_KEYWORDS,
    INDUSTRY_KEYWORDS,
    _business_tags_from_text,
    _classify_deadline_type,
    _condition_payload,
    _duplicate_group_key,
    _filter_columns_from_metadata,
    _gov24_audience_specificity,
    _merge_gov24_business_status_tags,
    _merge_industry_condition_with_codes,
    _normalize_status,
    _parse_datetime,
    _parse_deadline_range,
    _source_metadata,
    _stable_short_key,
    _status_from_deadline,
)
from app.services.normalization.persistence import (
    _replace_documents,
    _sync_sbiz24_attachments,
    _upsert_policy,
)
from app.services.normalization.regions import _extract_region_metadata
from app.services.normalization.source_documents import (
    _gov24_documents,
    _sbiz24_documents,
    _sections_from_sbiz24_text,
    _sections_from_semas,
    _semas_documents,
)

def _normalize_sbiz24(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    rows = (
        db.query(PolicyAnnouncement)
        .options(selectinload(PolicyAnnouncement.attachments))
        .all()
    )
    print(f"[normalizer] sbiz24: Found {len(rows)} raw policies to normalize.", flush=True)
    updated_count = 0
    progress_stats = _empty_progress_stats()

    for processed, row in enumerate(rows, start=1):
        attachment_texts = []
        existing_policy = (
            db.query(NormalizedPolicy)
            .filter(
                NormalizedPolicy.source == "sbiz24",
                NormalizedPolicy.source_pk == str(row.pbanc_sn),
            )
            .first()
        )
        if existing_policy:
            for link in existing_policy.attachments:
                if link.file and link.file.extracted_text:
                    attachment_texts.append(link.file.extracted_text)

        sections = _sections_from_sbiz24_text(row.content_text)
        metadata = _source_metadata(
            source="sbiz24",
            source_hash=row.content_hash,
            existing_llm_cache=_llm_cache_from_policy(existing_policy),
            title=row.title,
            category=row.category,
            target_text=row.target,
            content_text=row.content_text,
            sections=sections,
            region_text=_join_text(
                [
                    row.target,
                    _first_section_text_by_type(sections, "eligibility"),
                ]
            ),
            region_fallback_text=row.title,
            attachment_texts=attachment_texts,
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
            "apply_url": _first_text(
                (row.raw_detail_json or {}).get("data", {}).get("default", {}).get("bizAplySiteUrlAddr"),
                row.detail_url,
            ),
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
                "industry_condition": metadata["industry_condition"],
                "employee_limit": metadata["employee_limit"],
                "sales_limit": metadata["sales_limit"],
                "business_age_limit": metadata["business_age_limit"],
                "money_conditions": metadata["money_conditions"],
                "application_methods": metadata["application_methods"],
                "contacts": metadata["contacts"],
                "llm_cache": metadata["llm_cache"],
                "extraction_method": "rule",
                "deadline_type": _classify_deadline_type(_join_text([row.apply_start, row.apply_end, row.status])),
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

        if action != "unchanged":
            updated_count += 1
        _record_progress(progress_stats, payload)
        _log_progress(
            source="sbiz24",
            processed=processed,
            total=len(rows),
            current_title=row.title,
            action_stats=stats,
            field_stats=progress_stats,
        )

    print(f"[normalizer] sbiz24: Completed. Updated/Created: {updated_count} / {len(rows)}", flush=True)
    return stats


def _normalize_semas(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    rows = (
        db.query(PolicyProgramPage)
        .all()
    )
    print(f"[normalizer] semas: Found {len(rows)} raw policies to normalize.", flush=True)
    updated_count = 0
    progress_stats = _empty_progress_stats()

    for processed, row in enumerate(rows, start=1):
        source_pk = _stable_short_key(row.source_url)
        attachment_texts = []
        existing_policy = (
            db.query(NormalizedPolicy)
            .filter(
                NormalizedPolicy.source == "semas",
                NormalizedPolicy.source_pk == source_pk,
            )
            .first()
        )
        if existing_policy:
            for link in existing_policy.attachments:
                if link.file and link.file.extracted_text:
                    attachment_texts.append(link.file.extracted_text)

        sections = _sections_from_semas(row)
        metadata = _source_metadata(
            source="semas",
            source_hash=row.content_hash,
            existing_llm_cache=_llm_cache_from_policy(existing_policy),
            title=row.program_name,
            category=row.category,
            target_text=None,
            content_text=row.content_text,
            sections=sections,
            extra_texts=row.raw_breadcrumbs_json or [],
            default_business_status_tags=["small_business"],
            region_text=_first_section_text_by_type(sections, "eligibility"),
            region_fallback_text=_join_text(
                [row.program_name, *[_as_text(item) for item in (row.raw_breadcrumbs_json or [])]]
            ),
            attachment_texts=attachment_texts,
        )
        target_text = metadata["target_text"]
        support_content = _first_text(metadata["support_content_text"], row.content_text)
        docs = _semas_documents(row, sections, metadata)
        filter_columns = _filter_columns_from_metadata(metadata)

        deadline_text = _first_section_text_by_type(sections, "deadline") or _first_section_text_by_type(sections, "application")
        apply_start, apply_end = _parse_deadline_range(deadline_text)
        status = _status_from_deadline(deadline_text, apply_start, apply_end) or "notice"

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
            "status": status,
            "apply_start": apply_start,
            "apply_end": apply_end,
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
                "industry_condition": metadata["industry_condition"],
                "employee_limit": metadata["employee_limit"],
                "sales_limit": metadata["sales_limit"],
                "business_age_limit": metadata["business_age_limit"],
                "money_conditions": metadata["money_conditions"],
                "application_methods": metadata["application_methods"],
                "contacts": metadata["contacts"],
                "llm_cache": metadata["llm_cache"],
                "extraction_method": "rule",
                "deadline_text": deadline_text,
                "deadline_type": _classify_deadline_type(deadline_text),
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

        if action != "unchanged":
            updated_count += 1
        _record_progress(progress_stats, payload)
        _log_progress(
            source="semas",
            processed=processed,
            total=len(rows),
            current_title=row.program_name,
            action_stats=stats,
            field_stats=progress_stats,
        )

    print(f"[normalizer] semas: Completed. Updated/Created: {updated_count} / {len(rows)}", flush=True)
    return stats


def _normalize_gov24(db: Session) -> dict[str, int]:
    stats = _empty_stats()
    list_rows = (
        db.query(Gov24ServiceList)
        .all()
    )
    print(f"[normalizer] gov24: Found {len(list_rows)} raw policies to normalize.", flush=True)
    updated_count = 0
    progress_stats = _empty_progress_stats()

    for processed, list_row in enumerate(list_rows, start=1):
        detail = db.get(Gov24ServiceDetail, list_row.service_id)
        condition = db.get(Gov24SupportCondition, list_row.service_id)
        source_hash = _make_hash(
            [
                list_row.content_hash,
                detail.content_hash if detail else None,
                condition.content_hash if condition else None,
            ]
        )
        existing_policy = (
            db.query(NormalizedPolicy)
            .filter(
                NormalizedPolicy.source == "gov24",
                NormalizedPolicy.source_pk == list_row.service_id,
            )
            .first()
        )
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
        organization_name = _first_text(
            detail.organization_name if detail else None,
            list_row.organization_name,
        )
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
                target_text,
                _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
            ]
        ) or body
        region = _extract_region_metadata(
            _join_text(
                [
                    target_text,
                    _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                ]
            ),
            default_scope="national",
            fallback_text=list_row.service_name,
            supporting_text=organization_name,
        )
        text_industry_condition = _extract_industry_condition(
            gov_eligibility_blob,
            INDUSTRY_KEYWORDS,
        )
        industry_condition = _merge_industry_condition_with_codes(
            text_industry_condition,
            condition_payload["industry_tags"],
        )
        business_status_tags = _merge_gov24_business_status_tags(
            condition_payload["business_status_tags"],
            _tags_from_keyword_map(gov_eligibility_blob, BUSINESS_STATUS_KEYWORDS),
            list_row.user_type,
        )
        audience_specificity = _gov24_audience_specificity(
            list_row.user_type,
            target_text,
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
        gov_emp = _extract_employee_limit(gov_eligibility_blob)
        gov_sales = _extract_sales_limit(gov_eligibility_blob)
        gov_age = _extract_business_age_limit(gov_eligibility_blob)
        parsed_limits = {
            "employee_limit": gov_emp,
            "sales_limit": gov_sales,
            "business_age_limit": gov_age,
        }
        gov_limits, llm_cache = _resolve_limits_with_llm_cache(
            gov_eligibility_blob,
            parsed_limits,
            source_hash=source_hash,
            existing_llm_cache=_llm_cache_from_policy(existing_policy),
            log_label=f"gov24 '{list_row.service_name[:30]}'",
        )

        gov_emp = gov_limits["employee_limit"]
        gov_sales = gov_limits["sales_limit"]
        gov_age = gov_limits["business_age_limit"]

        gov_metadata = {
            "region": region,
            "required_documents": docs_required,
            "application_methods": _extract_application_methods(application_method),
            "contacts": contacts,
            "employee_limit": gov_emp,
            "sales_limit": gov_sales,
            "business_age_limit": gov_age,
            "llm_cache": llm_cache,
        }
        filter_columns = _filter_columns_from_metadata(gov_metadata)
        payload = {
            "source": "gov24",
            "source_pk": list_row.service_id,
            "canonical_key": f"gov24:{list_row.service_id}",
            "duplicate_group_key": _duplicate_group_key(list_row.service_name, list_row.organization_name),
            "title": list_row.service_name,
            "summary": _first_text(list_row.service_purpose_summary, _summarize(support_content), list_row.service_name),
            "body": body,
            "organization": organization_name,
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
            "industry_tags": industry_condition["include_tags"],
            "business_status_tags": business_status_tags,
            "eligibility": {
                "source": "gov24",
                "user_type": list_row.user_type,
                "audience_specificity": audience_specificity,
                "service_field": list_row.service_field,
                "selection_criteria": _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
                "application_deadline": application_deadline,
                "application_methods": filter_columns["application_methods"],
                "contacts": filter_columns["contact_points"],
                "region": region,
                "industry_tags": industry_condition["include_tags"],
                "industry_condition": industry_condition,
                "employee_limit": gov_metadata["employee_limit"],
                "sales_limit": gov_metadata["sales_limit"],
                "business_age_limit": gov_metadata["business_age_limit"],
                "money_conditions": _extract_money_conditions(gov_text_blob),
                "support_conditions": condition_payload["raw_flags"],
                "support_condition_labels": condition_payload["condition_labels"],
                "age": condition_payload["age"],
                "income_ranges": condition_payload["income_ranges"],
                "target_traits": condition_payload["target_traits"],
                "llm_cache": gov_metadata["llm_cache"],
                "extraction_method": "gov24_detail_and_condition_codes",
                "deadline_type": _classify_deadline_type(application_deadline),
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

        if action != "unchanged":
            updated_count += 1
        _record_progress(progress_stats, payload)
        _log_progress(
            source="gov24",
            processed=processed,
            total=len(list_rows),
            current_title=list_row.service_name,
            action_stats=stats,
            field_stats=progress_stats,
        )

    print(f"[normalizer] gov24: Completed. Updated/Created: {updated_count} / {len(list_rows)}", flush=True)
    return stats



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


def _empty_progress_stats() -> dict[str, int]:
    return {
        "required_documents": 0,
        "region_confirmed": 0,
        "region_needs_review": 0,
        "industry_known": 0,
        "llm_cached_fields": 0,
    }


def _record_progress(progress: dict[str, int], payload: dict) -> None:
    eligibility = payload.get("eligibility") or {}
    region = eligibility.get("region") or {}
    region_mode = region.get("condition_mode")
    confidence = float(region.get("confidence") or 0)
    industry = eligibility.get("industry_condition") or {}

    progress["required_documents"] += len(payload.get("required_documents") or [])
    if region_mode in {"restricted", "unrestricted"}:
        key = "region_confirmed" if confidence >= 0.8 else "region_needs_review"
        progress[key] += 1
    if industry.get("mode") in {"restricted", "unrestricted"}:
        progress["industry_known"] += 1
    progress["llm_cached_fields"] += _llm_cache_entry_count(
        eligibility.get("llm_cache") or {}
    )


def _llm_cache_entry_count(cache: dict) -> int:
    count = len([key for key in cache if key != "required_documents"])
    document_cache = cache.get("required_documents") or {}
    document_entries = document_cache.get("entries") or {}
    return count + len(document_entries)


def _log_progress(
    *,
    source: str,
    processed: int,
    total: int,
    current_title: str | None,
    action_stats: dict[str, int],
    field_stats: dict[str, int],
) -> None:
    if processed % 25 != 0 and processed != total:
        return
    title = (_clean_text(current_title) or "-")[:45]
    print(
        f"[normalizer] {source}: progress={processed}/{total} "
        f"actions(created={action_stats['normalized_created']},"
        f"updated={action_stats['normalized_updated']},"
        f"unchanged={action_stats['normalized_unchanged']},"
        f"errors={action_stats['errors']}) "
        f"fields(docs={field_stats['required_documents']},"
        f"region_confirmed={field_stats['region_confirmed']},"
        f"region_review={field_stats['region_needs_review']},"
        f"industry_known={field_stats['industry_known']},"
        f"llm_cached={field_stats['llm_cached_fields']}) "
        f"current='{title}'",
        flush=True,
    )


def _merge_stats(target: dict[str, int | bool], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = int(target.get(key, 0)) + value
