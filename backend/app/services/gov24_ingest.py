from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.crawlers.gov24_client import Gov24Client
from app.models.gov24 import Gov24ServiceDetail, Gov24ServiceList, Gov24SupportCondition


LIST_FIELD_MAP = {
    "registration_datetime": "등록일시",
    "department_name": "부서명",
    "user_type": "사용자구분",
    "detail_url": "상세조회URL",
    "service_name": "서비스명",
    "service_purpose_summary": "서비스목적요약",
    "service_field": "서비스분야",
    "selection_criteria": "선정기준",
    "organization_name": "소관기관명",
    "organization_type": "소관기관유형",
    "organization_code": "소관기관코드",
    "modified_datetime": "수정일시",
    "application_deadline": "신청기한",
    "application_method": "신청방법",
    "contact_phone": "전화문의",
    "reception_institution": "접수기관",
    "view_count": "조회수",
    "support_content": "지원내용",
    "support_target": "지원대상",
    "support_type": "지원유형",
}

DETAIL_FIELD_MAP = {
    "required_docs_by_official": "공무원확인구비서류",
    "required_docs": "구비서류",
    "contact": "문의처",
    "laws": "법령",
    "identity_required_docs": "본인확인필요구비서류",
    "service_name": "서비스명",
    "service_purpose": "서비스목적",
    "selection_criteria": "선정기준",
    "organization_name": "소관기관명",
    "modified_date": "수정일시",
    "application_deadline": "신청기한",
    "application_method": "신청방법",
    "online_application_url": "온라인신청사이트URL",
    "local_laws": "자치법규",
    "reception_institution_name": "접수기관명",
    "support_content": "지원내용",
    "support_target": "지원대상",
    "support_type": "지원유형",
    "administrative_rules": "행정규칙",
}

SUPPORT_CONDITION_FIELD_MAP = {
    "service_name": "서비스명",
    "ja0101_male": "JA0101",
    "ja0102_female": "JA0102",
    "ja0110_age_start": "JA0110",
    "ja0111_age_end": "JA0111",
    "ja0201_income_0_50": "JA0201",
    "ja0202_income_51_75": "JA0202",
    "ja0203_income_76_100": "JA0203",
    "ja0204_income_101_200": "JA0204",
    "ja0205_income_over_200": "JA0205",
    "ja0301_pre_parent_infertility": "JA0301",
    "ja0302_pregnant": "JA0302",
    "ja0303_childbirth_adoption": "JA0303",
    "ja0313_farmer": "JA0313",
    "ja0314_fisher": "JA0314",
    "ja0315_livestock_farmer": "JA0315",
    "ja0316_forester": "JA0316",
    "ja0317_elementary_student": "JA0317",
    "ja0318_middle_school_student": "JA0318",
    "ja0319_high_school_student": "JA0319",
    "ja0320_college_student": "JA0320",
    "ja0322_no_personal_trait": "JA0322",
    "ja0326_worker": "JA0326",
    "ja0327_job_seeker": "JA0327",
    "ja0328_disabled": "JA0328",
    "ja0329_veteran": "JA0329",
    "ja0330_disease_patient": "JA0330",
    "ja0401_multicultural_family": "JA0401",
    "ja0402_north_korean_defector": "JA0402",
    "ja0403_single_parent_grandparent_family": "JA0403",
    "ja0404_single_person_household": "JA0404",
    "ja0410_no_household_trait": "JA0410",
    "ja0411_multi_child_family": "JA0411",
    "ja0412_homeless_household": "JA0412",
    "ja0413_new_resident": "JA0413",
    "ja0414_extended_family": "JA0414",
    "ja1101_pre_founder": "JA1101",
    "ja1102_operating_business": "JA1102",
    "ja1103_closing_business": "JA1103",
    "ja1201_restaurant_business": "JA1201",
    "ja1202_manufacturing_business": "JA1202",
    "ja1299_other_business": "JA1299",
    "ja2101_small_medium_business": "JA2101",
    "ja2102_social_welfare_facility": "JA2102",
    "ja2103_institution_group": "JA2103",
    "ja2201_company_manufacturing": "JA2201",
    "ja2202_company_agriculture_fishery_forestry": "JA2202",
    "ja2203_company_information_communication": "JA2203",
    "ja2299_company_other_business": "JA2299",
}


def crawl_gov24_once() -> dict[str, dict[str, int] | bool]:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    locked = False
    stats: dict[str, dict[str, int] | bool] = {
        "locked": False,
        "service_list": _empty_stats(),
        "service_detail": _empty_stats(),
        "support_conditions": _empty_stats(),
    }

    try:
        locked = _try_advisory_lock(db)
        stats["locked"] = locked
        if not locked:
            return stats

        with Gov24Client() as client:
            service_list_rows = client.fetch_service_lists()
            service_ids = _extract_service_ids(service_list_rows)
            stats["service_list"] = _ingest_rows(
                db=db,
                rows=service_list_rows,
                model=Gov24ServiceList,
                field_map=LIST_FIELD_MAP,
            )

            service_detail_rows = _filter_rows_by_service_ids(
                client.fetch_service_details(),
                service_ids,
            )
            stats["service_detail"] = _ingest_rows(
                db=db,
                rows=service_detail_rows,
                model=Gov24ServiceDetail,
                field_map=DETAIL_FIELD_MAP,
            )

            support_condition_rows = _filter_rows_by_service_ids(
                client.fetch_support_conditions(),
                service_ids,
            )
            stats["support_conditions"] = _ingest_rows(
                db=db,
                rows=support_condition_rows,
                model=Gov24SupportCondition,
                field_map=SUPPORT_CONDITION_FIELD_MAP,
            )

        return stats
    finally:
        if locked:
            _release_advisory_lock(db)
        db.close()


def _ingest_rows(
    db: Session,
    rows: list[dict[str, Any]],
    model: type[Gov24ServiceList] | type[Gov24ServiceDetail] | type[Gov24SupportCondition],
    field_map: dict[str, str],
) -> dict[str, int]:
    stats = _empty_stats()
    stats["fetched"] = len(rows)
    seen_service_ids: set[str] = set()

    for row in rows:
        try:
            item_stats, service_id = _ingest_row(db, row, model, field_map)
            seen_service_ids.add(service_id)
            for key, value in item_stats.items():
                stats[key] += value
        except Exception as exc:
            db.rollback()
            stats["errors"] += 1
            print(f"[gov24-crawler] row failed table={model.__tablename__}: {exc}", flush=True)

    stats["deleted"] = _delete_missing(db, model, seen_service_ids)
    db.commit()
    return stats


def _ingest_row(
    db: Session,
    row: dict[str, Any],
    model: type[Gov24ServiceList] | type[Gov24ServiceDetail] | type[Gov24SupportCondition],
    field_map: dict[str, str],
) -> tuple[dict[str, int], str]:
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    service_id = _as_text(row.get("서비스ID"))
    if not service_id:
        raise ValueError(f"Missing 서비스ID: {row}")

    attrs = _build_attrs(row, field_map)
    attrs["service_id"] = service_id
    if not attrs.get("service_name"):
        attrs["service_name"] = service_id
    attrs["raw_json"] = row
    attrs["content_hash"] = _make_content_hash(row)
    attrs["last_seen_at"] = datetime.now(timezone.utc)
    attrs["is_active"] = True

    existing = db.get(model, service_id)
    if existing is None:
        attrs["first_seen_at"] = attrs["last_seen_at"]
        db.add(model(**attrs))
        stats["created"] += 1
    else:
        if existing.content_hash == attrs["content_hash"]:
            stats["unchanged"] += 1
        else:
            stats["updated"] += 1

        for key, value in attrs.items():
            setattr(existing, key, value)

    return stats, service_id


def _build_attrs(row: dict[str, Any], field_map: dict[str, str]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for attr_name, source_key in field_map.items():
        value = row.get(source_key)
        if attr_name == "view_count":
            attrs[attr_name] = _as_int(value)
        else:
            attrs[attr_name] = _as_text(value)
    return attrs


def _extract_service_ids(rows: list[dict[str, Any]]) -> set[str]:
    service_ids: set[str] = set()
    for row in rows:
        service_id = _as_text(row.get("서비스ID"))
        if service_id:
            service_ids.add(service_id)
    return service_ids


def _filter_rows_by_service_ids(
    rows: list[dict[str, Any]],
    service_ids: set[str],
) -> list[dict[str, Any]]:
    if not service_ids:
        return []
    return [row for row in rows if _as_text(row.get("서비스ID")) in service_ids]


def _delete_missing(
    db: Session,
    model: type[Gov24ServiceList] | type[Gov24ServiceDetail] | type[Gov24SupportCondition],
    seen_service_ids: set[str],
) -> int:
    if not seen_service_ids:
        return 0

    stale_rows = (
        db.query(model)
        .filter(model.service_id.notin_(seen_service_ids))
        .all()
    )
    for row in stale_rows:
        db.delete(row)
    return len(stale_rows)


def _empty_stats() -> dict[str, int]:
    return {
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "deleted": 0,
        "errors": 0,
    }


def _try_advisory_lock(db: Session) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": settings.GOV24_ADVISORY_LOCK_ID},
        ).scalar()
    )


def _release_advisory_lock(db: Session) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": settings.GOV24_ADVISORY_LOCK_ID},
    )
    db.commit()


def _as_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip() or None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _make_content_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
