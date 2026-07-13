from __future__ import annotations

import hashlib
import json
import calendar
import re
import httpx
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
    "이용대상": "eligibility",
    "이용 대상": "eligibility",
    "신청대상": "eligibility",
    "신청 대상": "eligibility",
    "지원자격": "eligibility",
    "지원 자격": "eligibility",
    "자격요건": "eligibility",
    "자격 요건": "eligibility",
    "가입대상": "eligibility",
    "가입 대상": "eligibility",
    "가입기준": "eligibility",
    "가입 기준": "eligibility",
    "가입요건": "eligibility",
    "가입 요건": "eligibility",
    "대상자": "eligibility",
    "대상자 기준": "eligibility",
    "제한기준": "restriction",
    "제한 기준": "restriction",
    "지원제외": "restriction",
    "지원 제외": "restriction",
    "제외대상": "restriction",
    "제외 대상": "restriction",
    "이용용도": "purpose",
    "이용 용도": "purpose",
    "이용료": "cost",
    "이용 료": "cost",
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
    "제출서류 및 신청양식": "requirements",
    "제출서류 안내": "requirements",
    "제출서류 양식": "requirements",
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

SIGUNGU_TO_SIDO = {
    "수원": "경기도", "성남": "경기도", "의정부": "경기도", "안양": "경기도", "부천": "경기도",
    "광명": "경기도", "평택": "경기도", "동두천": "경기도", "안산": "경기도", "고양": "경기도",
    "과천": "경기도", "구리": "경기도", "남양주": "경기도", "오산": "경기도", "시흥": "경기도",
    "군포": "경기도", "의왕": "경기도", "하남": "경기도", "용인": "경기도", "파주": "경기도",
    "이천": "경기도", "안성": "경기도", "김포": "경기도", "화성": "경기도", "양주": "경기도",
    "포천": "경기도", "여주": "경기도", "연천": "경기도", "가평": "경기도", "양평": "경기도",
    "동탄": "경기도",
    "춘천": "강원특별자치도", "원주": "강원특별자치도", "강릉": "강원특별자치도", "동해": "강원특별자치도",
    "태백": "강원특별자치도", "속초": "강원특별자치도", "삼척": "강원특별자치도", "홍천": "강원특별자치도",
    "횡성": "강원특별자치도", "영월": "강원특별자치도", "평창": "강원특별자치도", "정선": "강원특별자치도",
    "철원": "강원특별자치도", "화천": "강원특별자치도", "양구": "강원특별자치도", "인제": "강원특별자치도",
    "고성": "강원특별자치도", "양양": "강원특별자치도",
    "청주": "충청북도", "충주": "충청북도", "제천": "충청북도", "보은": "충청북도", "옥천": "충청북도",
    "영동": "충청북도", "증평": "충청북도", "진천": "충청북도", "괴산": "충청북도", "음성": "충청북도",
    "단양": "충청북도",
    "천안": "충청남도", "공주": "충청남도", "보령": "충청남도", "아산": "충청남도", "서산": "충청남도",
    "논산": "충청남도", "계룡": "충청남도", "당진": "충청남도", "금산": "충청남도", "부여": "충청남도",
    "서천": "충청남도", "청양": "충청남도", "홍성": "충청남도", "예산": "충청남도", "태안": "충청남도",
    "전주": "전북특별자치도", "군산": "전북특별자치도", "익산": "전북특별자치도", "정읍": "전북특별자치도",
    "남원": "전북특별자치도", "김제": "전북특별자치도", "완주": "전북특별자치도", "진안": "전북특별자치도",
    "무주": "전북특별자치도", "장수": "전북특별자치도", "임실": "전북특별자치도", "순창": "전북특별자치도",
    "고창": "전북특별자치도", "부안": "전북특별자치도",
    "목포": "전라남도", "여수": "전라남도", "순천": "전라남도", "나주": "전라남도", "광양": "전라남도",
    "담양": "전라남도", "곡성": "전라남도", "구례": "전라남도", "고흥": "전라남도", "보성": "전라남도",
    "화순": "전라남도", "장흥": "전라남도", "강진": "전라남도", "해남": "전라남도", "영암": "전라남도",
    "무안": "전라남도", "함평": "전라남도", "영광": "전라남도", "장성": "전라남도", "완도": "전라남도",
    "진도": "전라남도", "신안": "전라남도",
    "포항": "경상북도", "경주": "경상북도", "김천": "경상북도", "안동": "경상북도", "구미": "경상북도",
    "영주": "경상북도", "영천": "경상북도", "상주": "경상북도", "문경": "경상북도", "경산": "경상북도",
    "군위": "대구광역시", "의성": "경상북도", "청송": "경상북도", "영양": "경상북도", "영덕": "경상북도",
    "청도": "경상북도", "고령": "경상북도", "성주": "경상북도", "칠곡": "경상북도", "예천": "경상북도",
    "봉화": "경상북도", "울진": "경상북도", "울릉": "경상북도",
    "창원": "경상남도", "진주": "경상남도", "통영": "경상남도", "사천": "경상남도", "김해": "경상남도",
    "밀양": "경상남도", "거제": "경상남도", "양산": "경상남도", "의령": "경상남도", "함안": "경상남도",
    "창녕": "경상남도", "고성": "경상남도", "남해": "경상남도", "하동": "경상남도", "산청": "경상남도",
    "함양": "경상남도", "거창": "경상남도", "합천": "경상남도",
    "서귀포": "제주특별자치도", "제주": "제주특별자치도"
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
    print("[normalizer] Starting policy normalization job...", flush=True)
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
            print("[normalizer] Aborted. Normalization job is already locked by another process.", flush=True)
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

        print(f"[normalizer] Normalization job finished. Stats: {stats}", flush=True)
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
    print(f"[normalizer] sbiz24: Found {len(rows)} raw policies to normalize.", flush=True)
    updated_count = 0

    for row in rows:
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
            print(f"  [sbiz24] Policy '{row.title}' (ID: {row.pbanc_sn}) was {action}.", flush=True)

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

    for row in rows:
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
                "employee_limit": metadata["employee_limit"],
                "sales_limit": metadata["sales_limit"],
                "business_age_limit": metadata["business_age_limit"],
                "money_conditions": metadata["money_conditions"],
                "application_methods": metadata["application_methods"],
                "contacts": metadata["contacts"],
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
            print(f"  [semas] Policy '{row.program_name}' was {action}.", flush=True)

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
                target_text,
                _first_text(detail.selection_criteria if detail else None, list_row.selection_criteria),
            ]
        ) or body
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
        gov_emp = _extract_employee_limit(gov_eligibility_blob)
        gov_sales = _extract_sales_limit(gov_eligibility_blob)
        gov_age = _extract_business_age_limit(gov_eligibility_blob)
        gov_limits = {
            "employee_limit": gov_emp,
            "sales_limit": gov_sales,
            "business_age_limit": gov_age,
        }
        llm_fields = _limit_fields_requiring_llm(gov_eligibility_blob, gov_limits)
        complex_fields: list[str] = []
        for field in llm_fields:
            complex_payload = _complex_limit_payload(field, gov_eligibility_blob)
            if complex_payload is not None:
                gov_limits[field] = complex_payload
                complex_fields.append(field)
        if complex_fields:
            print(
                f"  [LLM Structure] gov24 '{list_row.service_name[:30]}' 복합 조건 구조화 요청: {complex_fields}",
                flush=True,
            )
        if llm_fields and settings.REC_OLLAMA_BASE_URL:
            print(f"  [Ollama] gov24 '{list_row.service_name[:30]}' 규칙 판정 보완: {llm_fields}", flush=True)
            llm_limits = _extract_limits_via_ollama(gov_eligibility_blob, llm_fields)
            for field in llm_fields:
                if llm_limits.get(field) is not None:
                    gov_limits[field] = llm_limits[field]
            filled = [field for field in llm_fields if gov_limits[field] is not None]
            print(f"  [Ollama] gov24 '{list_row.service_name[:30]}' 결과 적용: {filled if filled else '추출 없음'}", flush=True)

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
            print(f"  [gov24] Policy '{list_row.service_name}' (ID: {list_row.service_id}) was {action}.", flush=True)

    print(f"[normalizer] gov24: Completed. Updated/Created: {updated_count} / {len(list_rows)}", flush=True)
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
            
        sub_sections = _sections_from_sbiz24_text(text_value)
        if sub_sections:
            for sub in sub_sections:
                sections.append(sub)
        else:
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
    attachment_texts: list[str] | None = None,
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
    eligibility_section = _first_section_text_by_type(sections, "eligibility")
    # 제목·카테고리에는 "창업", "현금" 같은 단어가 자격조건과 무관하게
    # 들어갈 수 있으므로 숫자 조건 파싱 문맥에서 제외한다.
    eligibility_text = _join_text([target_text, eligibility_section]) or text_blob

    business_status_tags = _merge_unique_lists(
        default_business_status_tags or [],
        _tags_from_keyword_map(eligibility_text, BUSINESS_STATUS_KEYWORDS),
    )
    industry_tags = _tags_from_keyword_map(eligibility_text, INDUSTRY_KEYWORDS)
    required_documents = _extract_required_documents(sections, source)
    
    if attachment_texts:
        for att_text in attachment_texts:
            for line in _split_requirement_lines(att_text):
                for name in _split_document_names(line):
                    if _is_weak_document_name(name):
                        continue
                    required_documents.append(
                        {
                            "name": name,
                            "description": "",
                            "source": source,
                            "confidence": 0.7,
                            "extraction_method": "attachment_rule",
                        }
                    )
        required_documents = _dedupe_dicts(required_documents, "name")

    application_text = _join_text(
        [
            _first_section_text_by_type(sections, "application"),
            _first_section_text_by_type(sections, "deadline"),
        ]
    )
    contacts_text = _first_section_text_by_type(sections, "contact")

    target_val = _first_text(_first_section_text_by_type(sections, "eligibility"), target_text)
    if not target_val and content_text:
        target_pattern = re.compile(
            r"(?:신청\s*대상|지원\s*대상|이용\s*대상|가입\s*대상|가입\s*기준|신청\s*자격|지원\s*자격)\s*[:：\s]*(.*?)(?:\n\s*\n|\n\s*(?:[○\-\d]|\w+\s*[:：]|\bQ\d|\b[A-Za-z]+)\s*|$)",
            re.DOTALL | re.IGNORECASE
        )
        match = target_pattern.search(content_text)
        if match:
            target_val = match.group(1).strip()

    limits = {
        "employee_limit": _extract_employee_limit(eligibility_text),
        "sales_limit": _extract_sales_limit(eligibility_text),
        "business_age_limit": _extract_business_age_limit(eligibility_text),
    }
    llm_fields = _limit_fields_requiring_llm(eligibility_text, limits)
    complex_fields: list[str] = []
    for field in llm_fields:
        complex_payload = _complex_limit_payload(field, eligibility_text)
        if complex_payload is not None:
            limits[field] = complex_payload
            complex_fields.append(field)
    if complex_fields:
        label = _first_text(title, source) or source
        print(f"  [LLM Structure] {source} '{label[:30]}' 복합 조건 구조화 요청: {complex_fields}", flush=True)
    if llm_fields and settings.REC_OLLAMA_BASE_URL:
        label = _first_text(title, source) or source
        print(f"  [Ollama] {source} '{label[:30]}' 규칙 판정 보완: {llm_fields}", flush=True)
        llm_limits = _extract_limits_via_ollama(eligibility_text, llm_fields)
        for field in llm_fields:
            if llm_limits.get(field) is not None:
                limits[field] = llm_limits[field]
        filled = [field for field in llm_fields if limits[field] is not None]
        print(f"  [Ollama] {source} '{label[:30]}' 결과 적용: {filled if filled else '추출 없음'}", flush=True)

    return {
        "region": _extract_region_metadata(region_text if region_text is not None else eligibility_text),
        "summary_text": _first_section_text_by_type(sections, "summary"),
        "target_text": target_val,
        "support_content_text": _first_section_text_by_type(sections, "support_content"),
        "required_documents": required_documents,
        "business_status_tags": business_status_tags,
        "industry_tags": industry_tags,
        "employee_limit": limits["employee_limit"],
        "sales_limit": limits["sales_limit"],
        "business_age_limit": limits["business_age_limit"],
        "money_conditions": _extract_money_conditions(text_blob),
        "application_methods": _extract_application_methods(application_text or text_blob),
        "contacts": _extract_contacts(_join_text([contacts_text, text_blob])),
    }


def _safe_int(val: Any, max_limit: int = 2147483647) -> int | None:
    if val is None:
        return None
    try:
        i = int(val)
        if -2147483648 <= i <= max_limit:
            return i
        return None
    except (ValueError, TypeError):
        return None


def _safe_bigint(val: Any) -> int | None:
    if val is None:
        return None
    try:
        i = int(val)
        if -9223372036854775808 <= i <= 9223372036854775807:
            return i
        return None
    except (ValueError, TypeError):
        return None


def _filter_columns_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    region = metadata.get("region") or {}
    required_documents = metadata.get("required_documents") or []
    employee_limit = metadata.get("employee_limit") or {}
    sales_limit = metadata.get("sales_limit") or {}
    business_age_limit = metadata.get("business_age_limit") or {}

    # 복합/분기 조건은 eligibility JSON에만 보존하고 단일 필터 컬럼에는 쓰지 않는다.
    # 그렇지 않으면 OR 분기의 숫자 하나가 전체 정책의 필수조건처럼 동작한다.
    flat_employee_limit = {} if employee_limit.get("requires_manual_review") else employee_limit
    flat_sales_limit = {} if sales_limit.get("requires_manual_review") else sales_limit
    flat_business_age_limit = (
        {} if business_age_limit.get("requires_manual_review") else business_age_limit
    )

    # 업력 조건의 경우 100년을 초과하는 값이 오면 LLM 파싱 오동작(예: 매출액을 업력에 대입)으로 판단하여 제외합니다.
    age_val = flat_business_age_limit.get("value")
    if age_val is not None:
        try:
            if int(age_val) > 100:
                age_val = None
        except (ValueError, TypeError):
            age_val = None

    return {
        "matched_sidos": region.get("matched_sidos") or [],
        "region_confidence": region.get("confidence"),
        "application_methods": metadata.get("application_methods") or [],
        "contact_points": metadata.get("contacts") or [],
        "employee_limit_value": _safe_int(flat_employee_limit.get("value")),
        "employee_limit_operator": flat_employee_limit.get("operator"),
        "sales_limit_amount_krw": _safe_bigint(flat_sales_limit.get("amount_krw")),
        "sales_limit_operator": flat_sales_limit.get("operator"),
        "business_age_limit_value": _safe_int(age_val),
        "business_age_limit_operator": flat_business_age_limit.get("operator") if age_val is not None else None,
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

    sigungu_val = None
    if not matched_sidos:
        for sigungu, sido in SIGUNGU_TO_SIDO.items():
            pattern = rf"(?<![가-힣]){re.escape(sigungu)}(?:시|군|구)?(?![가-힣])"
            match = re.search(pattern, text_value)
            if match:
                if sido not in matched_sidos:
                    matched_sidos.append(sido)
                sigungu_val = match.group(0)
                break

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

    if sigungu_val is None:
        sigungu = _extract_sigungu_after_sido(text_value, matched_sidos) if matched_sidos else None
    else:
        sigungu = sigungu_val

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
        "제출서류 안내",
        "제출 서류 안내",
        "제출서류 목록",
        "제출 서류 목록",
        "제출서류 리스트",
        "제출 서류 리스트",
        "제출서류 확인",
        "제출 서류 확인",
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
        r"((?:[가-힣A-Za-z0-9·ㆍ/&()\-]+업)[^0-9]{0,10}(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        operator, source_text = _operator_and_source_for_limit(text_value, match, match.group(3))
        return {
            "value": int(match.group(2)),
            "operator": operator,
            "unit": "people",
            "source_text": source_text,
            "extraction_method": "rule",
        }
    return None


def _extract_sales_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None

    # ``1억 4백만원``처럼 억 단위와 하위 단위가 섞인 금액은 기존의
    # 단일 숫자+단위 정규식으로는 1억원으로 잘려 저장된다.
    mixed_pattern = re.compile(
        r"((?:연\s*)?(?:전년도\s*)?(?:매출액?|연매출)[^0-9]{0,25}"
        r"(\d+(?:,\d{3})*)\s*억\s*"
        r"(?:(\d+(?:,\d{3})*)\s*(천만|백만|만)\s*원?)?"
        r"\s*(미만|이하|이상|초과)?)"
    )
    mixed_match = mixed_pattern.search(text_value)
    if mixed_match and mixed_match.group(3) and mixed_match.group(4):
        amount = int(mixed_match.group(2).replace(",", "")) * 100_000_000
        subunit_multiplier = {
            "천만": 10_000_000,
            "백만": 1_000_000,
            "만": 10_000,
        }[mixed_match.group(4)]
        amount += int(mixed_match.group(3).replace(",", "")) * subunit_multiplier
        operator, source_text = _operator_and_source_for_limit(
            text_value,
            mixed_match,
            mixed_match.group(5) or "이하",
        )
        return {
            "amount_krw": amount,
            "operator": operator,
            "source_text": source_text,
            "extraction_method": "rule",
        }

    pattern = re.compile(
        r"((?:연\s*)?(?:전년도\s*)?(?:매출액?|연매출)[^0-9]{0,25}"
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
        r"\s*(미만|이하|이상|초과)?)"
    )
    match = pattern.search(text_value)
    if not match:
        return None
    operator, source_text = _operator_and_source_for_limit(text_value, match, match.group(4) or "이하")
    return {
        "amount_krw": _money_to_krw(match.group(2), match.group(3)),
        "operator": operator,
        "source_text": source_text,
        "extraction_method": "rule",
    }


def _extract_business_age_limit(value: str | None) -> dict[str, Any] | None:
    text_value = _clean_text(value)
    if not text_value:
        return None
    patterns = [
        r"((?:창업|업력|영업기간|운영기간|영업개시|설립|개업일|등록일)[^0-9]{0,12}"
        r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과))",
        r"((?:사업자\s*등록(?:일)?|사업\s*개시일?|사업개시일)"
        r"(?:\s*(?:후|부터|로부터|기준|경과))?[^0-9]{0,12}"
        r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과))",
        r"((\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과)[^.\n]{0,20}(?:창업|업력|사업자\s*등록|사업\s*개시))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if not match:
            continue
        limit_years = int(match.group(2))
        op_text = match.group(3)
        operator, source_text = _operator_and_source_for_limit(text_value, match, op_text)
        return {
            "value": limit_years,
            "operator": operator,
            "unit": "years",
            "source_text": source_text,
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
        "경과": ">=",
        "한도": "<=",
        "까지": "<=",
        "내외": "~",
    }.get(value, "<=")


def _direct_exclusion_match(tail: str) -> re.Match[str] | None:
    return re.search(
        r"^\s*(?:인\s*)?(?:업소|업체|기업|사업체|대상자)?\s*"
        r"(?:은|는|을|를)?\s*(?:지원\s*대상에서\s*)?"
        r"(?:제외|지원\s*불가)(?!\s*업종)",
        tail,
    )


def _operator_and_source_for_limit(text_value: str, match: re.Match[str], operator_text: str) -> tuple[str, str]:
    operator = _operator_symbol(operator_text)
    tail = text_value[match.end():match.end() + 40]
    exclusion_match = _direct_exclusion_match(tail)
    source_text = match.group(1)
    if exclusion_match:
        operator = {">=": "<", ">": "<=", "<=": ">", "<": ">="}.get(operator, operator)
        source_text = _clean_text(f"{source_text}{exclusion_match.group(0)}") or source_text
    return operator, source_text


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
    if not value:
        return None, None
        
    text_value = value.strip().replace(" ", "")  # 공백 제거하여 매칭 확률 증가
    
    # 1. 4자리 연도 패턴 YYYY.MM.DD (ex: 2026.03.03)
    matches_3_parts = re.findall(r"(20\d{2})[.\-/년]+(\d{1,2})[.\-/월]+(\d{1,2})", text_value)
    
    # 2. 2자리 연도 패턴 YY.MM.DD (ex: '25.2.24)
    if not matches_3_parts:
        matches_3_parts = []
        for y, m, d in re.findall(r"\b(2\d|3\d)[.\-/년]+(\d{1,2})[.\-/월]+(\d{1,2})", text_value):
            matches_3_parts.append((f"20{y}", m, d))
            
    dates: list[datetime] = []
    for year, month, day in matches_3_parts[:2]:
        try:
            dates.append(datetime(int(year), int(month), int(day)))
        except ValueError:
            continue
            
    if dates:
        if len(dates) == 1:
            first_date = dates[0]
            year = first_date.year
            # 매칭된 부분 제거
            remaining_text = re.sub(r"(?:20)?(?:2\d|3\d)[.\-/년]+\d{1,2}[.\-/월]+\d{1,2}", "", text_value, count=1)
            # 종료일이 월/일만 있는지 확인 (ex: ~10.30)
            second_match = re.search(r"(\d{1,2})[.\-/월]+(\d{1,2})", remaining_text)
            if second_match:
                try:
                    second_date = datetime(year, int(second_match.group(1)), int(second_match.group(2)))
                    if first_date <= second_date:
                        return first_date, _as_end_of_day(second_date)
                    else:
                        return second_date, _as_end_of_day(first_date)
                except ValueError:
                    pass
            if re.search(r"(?:예산|자금|보증규모|한도)?.{0,10}소진", remaining_text):
                return first_date, None
            return None, _as_end_of_day(first_date)
        return dates[0], _as_end_of_day(dates[1])

    # 3. 연/월만 명시된 경우 (YYYY.MM) 파싱 시도 (ex: 2026.2.~ / 2026년2월~12월)
    matches_2_parts = re.findall(r"(20\d{2})[.\-/년]+(\d{1,2})[.\-/월]*", text_value)
    if not matches_2_parts:
        matches_2_parts = []
        for y, m in re.findall(r"\b(2\d|3\d)[.\-/년]+(\d{1,2})[.\-/월]*", text_value):
            matches_2_parts.append((f"20{y}", m))
            
    if matches_2_parts:
        dates_2_parts = []
        for year, month in matches_2_parts[:2]:
            try:
                dates_2_parts.append((int(year), int(month)))
            except ValueError:
                continue
        if dates_2_parts:
            y1, m1 = dates_2_parts[0]
            start_date = datetime(y1, m1, 1)
            
            # 남은 텍스트에서 두 번째 월이 있는지 확인
            remaining_text = re.sub(r"(?:20)?(?:2\d|3\d)[.\-/년]+\d{1,2}[.\-/월]*", "", text_value, count=1)
            
            if len(dates_2_parts) == 2:
                y2, m2 = dates_2_parts[1]
                last_day = calendar.monthrange(y2, m2)[1]
                end_date = datetime(y2, m2, last_day)
                return start_date, _as_end_of_day(end_date)
            else:
                # 단독 월 추출 시도 (ex: ~12월)
                month_match = re.search(r"(\d{1,2})[월\s]*", remaining_text)
                if month_match:
                    try:
                        m2 = int(month_match.group(1))
                        last_day = calendar.monthrange(y1, m2)[1]
                        end_date = datetime(y1, m2, last_day)
                        return start_date, _as_end_of_day(end_date)
                    except ValueError:
                        pass
                if re.search(r"(?:예산|자금|보증규모|한도)?.{0,10}소진", remaining_text):
                    return start_date, None
                last_day = calendar.monthrange(y1, m1)[1]
                return start_date, _as_end_of_day(datetime(y1, m1, last_day))

    return None, None


def _classify_deadline_type(value: str | None) -> str:
    text_value = _clean_text(value) or ""
    if not text_value:
        return "unknown"
    if any(token in text_value for token in ("상시", "연중", "소진", "매일", "항시")):
        return "ongoing"
    if any(token in text_value for token in ("상이", "구분", "별도", "공고별")):
        return "various"
    if any(token in text_value for token in ("불필요", "없음")):
        return "none"
    if re.search(r"\d{4}[.\-/년\s]+\d{1,2}", text_value) or re.search(r"\d{1,2}[.\-/월\s]+\d{1,2}", text_value):
        return "fixed"
    return "other"


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


LIMIT_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "employee_limit": {
        # 공고마다 같은 개념을 ``근로자``, ``종사자``, ``상시인원`` 등으로
        # 다르게 표현하므로 현재 수집된 업종명만 나열하지 않습니다.
        "keywords": (
            "근로자",
            "상시근로자수",
            "직원",
            "종업원",
            "종사자",
            "고용인원",
            "상시인원",
            "근로 인원",
            "근무자",
        ),
        # 업종별 인원 기준은 업종명이 새로 추가되어도 후보로 보냅니다.
        "anchor_pattern": r"[가-힣A-Za-z0-9·ㆍ/&()\-]+업",
        "numeric_unit_pattern": r"\d+(?:,\d{3})*\s*(?:명|인)(?=\s*(?:미만|이하|이상|초과|약|내외|규모|$))",
        "maximum": 1_000_000,
    },
    "sales_limit": {
        "keywords": ("매출", "매출액", "연매출"),
        "numeric_unit_pattern": (
            r"\d+(?:,\d{3})*(?:\.\d+)?\s*"
            r"(?:억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)"
            r"(?=\s*(?:미만|이하|이상|초과|약|내외|범위|$))"
        ),
        "maximum": 9_000_000_000_000_000_000,
    },
    "business_age_limit": {
        "keywords": (
            "업력",
            "창업",
            "사업개시",
            "사업 개시",
            "사업자등록",
            "사업자 등록",
            "개업",
            "영업기간",
            "운영기간",
            "영업개시",
            "설립",
            "개업일",
            "등록일",
        ),
        "numeric_unit_pattern": r"\d+\s*년(?=\s*(?:미만|이하|이상|초과|이내|약|내외|경과|$))",
        "maximum": 100,
    },
}


def _limit_candidate_context(value: str | None, field: str) -> str | None:
    text_value = _clean_text(value)
    spec = LIMIT_FIELD_SPECS.get(field)
    if not text_value or not spec:
        return None

    spans: list[tuple[int, int]] = []
    qualifier_pattern = re.compile(r"미만|이하|이상|초과|이내|경과|약|내외|범위")
    numeric_unit_pattern = re.compile(spec["numeric_unit_pattern"])
    for keyword in spec["keywords"]:
        for match in re.finditer(re.escape(keyword), text_value, re.IGNORECASE):
            start = max(match.start() - 60, 0)
            end = min(match.end() + 140, len(text_value))
            window = text_value[start:end]
            numeric_matches = list(numeric_unit_pattern.finditer(window))
            if not numeric_matches:
                continue
            if not qualifier_pattern.search(window):
                continue
            keyword_start = match.start() - start
            keyword_end = match.end() - start
            is_near_keyword = any(
                min(abs(number.start() - keyword_end), abs(keyword_start - number.end())) <= 60
                for number in numeric_matches
            )
            if not is_near_keyword:
                continue
            spans.append((start, end))

    # 일부 공고는 "상시근로자"라는 말을 생략하고
    # "도소매·서비스업(5인 미만), 제조·건설업(10인 미만)"처럼 쓴다.
    # 업종 앵커가 있는 경우에만 직원 수 후보로 추가한다.
    if field == "employee_limit" and spec.get("anchor_pattern"):
        for match in re.finditer(spec["anchor_pattern"], text_value):
            start = max(match.start() - 20, 0)
            end = min(match.end() + 80, len(text_value))
            window = text_value[start:end]
            numeric_matches = list(numeric_unit_pattern.finditer(window))
            if not numeric_matches or not qualifier_pattern.search(window):
                continue
            spans.append((start, end))

    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    windows = [text_value[start:end] for start, end in merged]
    return _clean_text(" ... ".join(windows))


def _limit_fields_requiring_llm(
    text_value: str | None,
    parsed_limits: dict[str, dict[str, Any] | None],
) -> list[str]:
    requested: list[str] = []
    for field in LIMIT_FIELD_SPECS:
        context = _limit_candidate_context(text_value, field)
        if not context:
            continue
        parsed = parsed_limits.get(field)
        numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", context)
        has_lower = bool(re.search(r"이상|초과", context))
        has_upper = bool(re.search(r"이하|미만|이내|경과하지", context))
        is_two_sided_range = len(numbers) >= 2 and has_lower and has_upper
        is_complex = bool(_complex_limit_payload(field, context))
        if parsed is None or is_two_sided_range or is_complex:
            requested.append(field)
    return requested


def _select_limit_context(text_value: str, requested_fields: list[str]) -> str:
    selected = [
        context
        for field in requested_fields
        if (context := _limit_candidate_context(text_value, field))
    ]
    context = _clean_text(" ... ".join(dict.fromkeys(selected))) or text_value
    return context[: settings.NORMALIZE_LLM_MAX_CONTEXT_CHARS]


def _coerce_limit_int(value: Any, maximum: int) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    elif isinstance(value, str):
        compact = value.replace(",", "").strip()
        if not re.fullmatch(r"\d+", compact):
            return None
        parsed = int(compact)
    else:
        return None
    return parsed if 0 <= parsed <= maximum else None


def _normalize_llm_operator(value: Any, side: str, evidence: str) -> str | None:
    aliases = {
        "이상": ">=",
        "초과": ">",
        "이하": "<=",
        "미만": "<",
        "이내": "<=",
    }
    operator = aliases.get(str(value).strip(), str(value).strip()) if value is not None else None
    allowed = {">=", ">"} if side == "min" else {"<=", "<"}
    if operator in allowed:
        return operator
    if side == "min":
        if "초과" in evidence:
            return ">"
        if "이상" in evidence or ("경과" in evidence and "경과하지" not in evidence):
            return ">="
    else:
        if "미만" in evidence:
            return "<"
        if any(token in evidence for token in ("이하", "이내", "경과하지")):
            return "<="
    return None


def _numeric_match_has_field_context(
    field: str,
    evidence: str,
    numeric_match: re.Match[str],
    *,
    max_distance: int = 60,
) -> bool:
    spec = LIMIT_FIELD_SPECS[field]
    separators = re.compile(r"[。.!?;]|(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨|○|◦|▪|▶|▷|▸)")
    for keyword in spec["keywords"]:
        for keyword_match in re.finditer(re.escape(keyword), evidence, re.IGNORECASE):
            distance = min(
                abs(numeric_match.start() - keyword_match.end()),
                abs(keyword_match.start() - numeric_match.end()),
            )
            if distance > max_distance:
                continue
            start = min(keyword_match.end(), numeric_match.end())
            end = max(keyword_match.start(), numeric_match.start())
            between = evidence[start:end]
            if separators.search(between):
                continue
            if field == "sales_limit" and re.search(
                r"임차료|지원금|지원액|보증한도|대출한도|융자한도|자금한도|사업비",
                between,
            ):
                continue
            if field == "sales_limit" and "억" in evidence[max(0, numeric_match.start() - 6):numeric_match.start()]:
                # ``1억 4백만원``의 4백만원만 별도 매출액으로 해석하지 않는다.
                continue
            return True
    return False


def _bounds_from_evidence(field: str, evidence: str) -> dict[str, Any]:
    bounds: dict[str, Any] = {
        "min_value": None,
        "min_operator": None,
        "max_value": None,
        "max_operator": None,
        "constraints": [],
        "has_alternatives": False,
    }
    if field == "employee_limit":
        matches = re.finditer(r"(\d+)\s*(?:명|인)\s*(미만|이하|이상|초과)", evidence)
        extracted = [
            (int(match.group(1)), _operator_symbol(match.group(2)), match.group(0), match.end())
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]
    elif field == "sales_limit":
        matches = re.finditer(
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*"
            r"(억\s*원|억원|천만\s*원|천만원|백만\s*원|백만원|만\s*원|만원|원)\s*"
            r"(미만|이하|이상|초과)",
            evidence,
        )
        extracted = [
            (
                _money_to_krw(match.group(1), match.group(2)),
                _operator_symbol(match.group(3)),
                match.group(0),
                match.end(),
            )
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]
        direct_sales = _extract_sales_limit(evidence)
        if direct_sales and not any(
            item[0] == direct_sales["amount_krw"] and item[1] == direct_sales["operator"]
            for item in extracted
        ):
            extracted.insert(
                0,
                (
                    direct_sales["amount_krw"],
                    direct_sales["operator"],
                    direct_sales["source_text"],
                    -1,
                ),
            )
    else:
        matches = re.finditer(
            r"(\d+)\s*년\s*(이내|이하|미만|이상|초과|경과하지\s*(?:않은|아니한)|경과)",
            evidence,
        )
        extracted = [
            (int(match.group(1)), _operator_symbol(match.group(2)), match.group(0), match.end())
            for match in matches
            if _numeric_match_has_field_context(field, evidence, match)
        ]

    side_values: dict[str, set[int]] = {"min": set(), "max": set()}
    seen_constraints: set[tuple[int, str, str]] = set()
    for value, operator, source_text, match_end in extracted:
        tail = evidence[match_end:match_end + 40] if match_end >= 0 else ""
        exclusion_match = _direct_exclusion_match(tail) if tail else None
        if exclusion_match:
            operator = {">=": "<", ">": "<=", "<=": ">", "<": ">="}.get(operator, operator)
            source_text = _clean_text(f"{source_text}{exclusion_match.group(0)}") or source_text
        side = "min" if operator in {">", ">="} else "max"
        side_values[side].add(value)
        bounds[f"{side}_value"] = value
        bounds[f"{side}_operator"] = operator
        marker = (value, operator, source_text)
        if marker in seen_constraints:
            continue
        seen_constraints.add(marker)
        bounds["constraints"].append(
            {"value": value, "operator": operator, "source_text": source_text}
        )
    min_value = bounds["min_value"]
    max_value = bounds["max_value"]
    bounds["has_alternatives"] = (
        len(bounds["constraints"]) > 2
        or any(len(values) > 1 for values in side_values.values())
        or (min_value is not None and max_value is not None and min_value > max_value)
    )
    return bounds


def _branching_limit_reason(context: str, field: str) -> str | None:
    """단일 숫자로 평탄화하면 의미가 바뀌는 분기/관계 조건을 찾습니다."""
    all_required = bool(re.search(r"(?:모두|전부|모든).{0,12}(?:충족|해당|요건)", context))
    branch_markers = (
        "각 호 중",
        "다음 각 호",
        "중 1개",
        "중 하나",
        "어느 하나",
        "자금별",
        "유형별",
        "업종별",
    )
    if any(marker in context for marker in branch_markers):
        return "branching_condition"
    if not all_required and re.search(r"(?:^|\s)(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨)", context) and len(
        re.findall(r"(?:①|②|③|④|⑤|⑥|⑦|⑧|⑨)", context)
    ) >= 2:
        return "numbered_alternatives"
    if len(re.findall(r"(?:창업|경영개선|점포임차|대환|일반|우대)\s*자금\s*:", context)) >= 2:
        return "named_alternatives"
    if "또는" in context:
        return "or_condition"
    if field == "employee_limit" and any(
        marker in context for marker in ("과반수", "비율", "고용하고 유지", "고용하여 유지")
    ):
        return "relational_employee_condition"
    if field == "business_age_limit" and any(
        marker in context for marker in ("예비창업자", "사업자등록 말소", "최근")
    ):
        return "temporal_or_status_condition"
    return None


def _complex_limit_payload(field: str, text_value: str) -> dict[str, Any] | None:
    context = _limit_candidate_context(text_value, field)
    if not context:
        return None
    bounds = _bounds_from_evidence(field, context)
    branch_reason = _branching_limit_reason(context, field)
    # 후보 문맥 앞부분이 잘려 ①·②만 남는 경우가 있어, 전체 자격문맥에서
    # "모두 충족/모두 해당"이면 numbered_alternatives 오탐을 해제한다.
    if branch_reason == "numbered_alternatives" and re.search(
        r"(?:모두|전부|모든).{0,16}(?:충족|해당|요건)",
        _clean_text(text_value) or "",
    ):
        branch_reason = None
    if not bounds["has_alternatives"] and not branch_reason:
        return None
    result: dict[str, Any] = {
        "constraints": bounds["constraints"],
        "source_text": context,
        "extraction_method": "rule_ambiguous",
        "requires_manual_review": True,
        "logic": "any_of" if branch_reason else "all_of",
        "review_reason": branch_reason or "multiple_numeric_constraints",
    }
    if field == "sales_limit":
        result["unit"] = "krw"
    else:
        result["unit"] = "people" if field == "employee_limit" else "years"
    return result


def _convert_llm_limit(
    field: str,
    raw_value: Any,
    context: str,
    model_name: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_value, dict):
        return None

    evidence = _clean_text(_as_text(raw_value.get("evidence")))
    if not evidence or evidence not in context:
        return None
    if not _limit_candidate_context(evidence, field):
        return None

    maximum = int(LIMIT_FIELD_SPECS[field]["maximum"])
    evidence_bounds = _bounds_from_evidence(field, evidence)
    classification = (_as_text(raw_value.get("classification")) or "direct").lower()
    logic = (_as_text(raw_value.get("logic")) or "all_of").lower()
    scope = (_as_text(raw_value.get("scope")) or "global").lower()
    if classification in {"unrelated", "none", "not_eligibility"}:
        return None
    if classification in {"alternative", "complex", "relational"} or scope != "global":
        result: dict[str, Any] = {
            "constraints": evidence_bounds["constraints"],
            "source_text": evidence,
            "extraction_method": "ollama_structure",
            "model": model_name,
            "requires_manual_review": True,
            "logic": logic if logic in {"all_of", "any_of"} else "any_of",
            "review_reason": classification,
            "scope": scope,
        }
        result["unit"] = (
            "krw"
            if field == "sales_limit"
            else "people" if field == "employee_limit" else "years"
        )
        return result

    min_value = _coerce_limit_int(evidence_bounds["min_value"], maximum)
    max_value = _coerce_limit_int(evidence_bounds["max_value"], maximum)
    # evidence에서 하나라도 유효한 경계를 복구했다면, 모델이 별도로 생성한
    # 반대쪽 숫자는 신뢰하지 않는다. 다른 금액(임차료·지원금)을 min/max로
    # 끌어오는 소형 모델의 오탐을 막기 위한 규칙이다.
    if not evidence_bounds["constraints"]:
        min_value = _coerce_limit_int(raw_value.get("min"), maximum)
        max_value = _coerce_limit_int(raw_value.get("max"), maximum)
    min_operator = _as_text(evidence_bounds["min_operator"])
    max_operator = _as_text(evidence_bounds["max_operator"])
    if min_value is not None and min_operator is None:
        min_operator = _normalize_llm_operator(raw_value.get("min_operator"), "min", evidence)
    if max_value is not None and max_operator is None:
        max_operator = _normalize_llm_operator(raw_value.get("max_operator"), "max", evidence)

    if min_value is not None and min_operator is None:
        min_value = None
    if max_value is not None and max_operator is None:
        max_value = None
    if min_value is None and max_value is None:
        return None
    if min_value is not None and max_value is not None and min_value > max_value:
        return None

    result: dict[str, Any] = {
        "min_value": min_value,
        "min_operator": min_operator,
        "max_value": max_value,
        "max_operator": max_operator,
        "source_text": evidence,
        "extraction_method": "ollama_llm",
        "model": model_name,
    }
    if field == "sales_limit":
        result["min_amount_krw"] = min_value
        result["max_amount_krw"] = max_value
        if (min_value is None) != (max_value is None):
            result["amount_krw"] = max_value if max_value is not None else min_value
            result["operator"] = max_operator if max_value is not None else min_operator
    else:
        result["unit"] = "people" if field == "employee_limit" else "years"
        if (min_value is None) != (max_value is None):
            result["value"] = max_value if max_value is not None else min_value
            result["operator"] = max_operator if max_value is not None else min_operator
    return result


def _extract_limits_via_ollama(
    text_value: str | None,
    requested_fields: list[str] | None = None,
) -> dict[str, Any]:
    """규칙으로 확정하지 못한 조건을 구조화하되, 근거는 코드로 재검증합니다."""
    fallback_res = {field: None for field in LIMIT_FIELD_SPECS}
    clean_txt = _clean_text(text_value)
    if not clean_txt:
        return fallback_res

    fields = [field for field in (requested_fields or LIMIT_FIELD_SPECS.keys()) if field in LIMIT_FIELD_SPECS]
    fields = [field for field in fields if _limit_candidate_context(clean_txt, field)]
    if not fields:
        return fallback_res

    model_name = settings.NORMALIZE_LLM_MODEL
    base_url = settings.REC_OLLAMA_BASE_URL
    if not base_url:
        return fallback_res

    field_prompts = {
        "employee_limit": (
            "사업체 직원수 또는 상시근로자수 조건",
            "입력 '상시근로자 5인 미만'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":null,"min_operator":null,"max":5,"max_operator":"<","evidence":"상시근로자 5인 미만"}',
        ),
        "sales_limit": (
            "사업체의 연간 매출액 조건",
            "입력 '연매출 10억원 이하'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":null,"min_operator":null,"max":1000000000,"max_operator":"<=","evidence":"연매출 10억원 이하"}',
        ),
        "business_age_limit": (
            "사업체의 창업 후 업력 조건",
            "입력 '창업 3년 이상 7년 이하'이면 "
            '{"classification":"direct","logic":"all_of","scope":"global",'
            '"min":3,"min_operator":">=","max":7,"max_operator":"<=","evidence":"창업 3년 이상 7년 이하"}',
        ),
    }

    for field in fields:
        complex_payload = _complex_limit_payload(field, clean_txt)
        context = _select_limit_context(clean_txt, [field])
        description, example = field_prompts[field]
        system_prompt = (
            f"당신은 소상공인 지원 공고에서 {description} 하나만 추출합니다. "
            "반드시 classification, logic, scope, min, min_operator, max, max_operator, evidence 키를 가진 "
            "단일 JSON 객체를 반환하세요. classification은 direct, alternative, relational, unrelated 중 하나입니다. "
            "logic은 all_of 또는 any_of, scope는 global 또는 branch입니다. "
            "미만은 <, 이하는 <=, 초과는 >, 이상은 >= 입니다. "
            "명시된 숫자 조건이 없을 때만 min과 max를 null로 두세요. "
            "소상공인이라는 단어만으로 기준을 추정하지 마세요. "
            "지원금액, 대표자 나이, 예상 매출은 자격조건으로 해석하지 마세요. "
            "각 호 중 하나, 또는, 자금별·업종별 조건은 direct로 평탄화하지 마세요. "
            "매출액은 원 단위 정수로 환산하고, 양쪽 범위는 min과 max를 모두 보존하세요. "
            "evidence는 해당 필드의 숫자 조건이 담긴 가장 짧은 연속 원문만 그대로 복사하고, "
            "임차료·지원금·대표자 나이·신용점수 등 다른 숫자는 포함하지 마세요. "
            f"출력 예시: {example}. JSON 이외의 문장은 출력하지 마세요."
        )
        print(f"  [Ollama Structure] {model_name} 호출: field={field}, chars={len(context)}", flush=True)
        try:
            response = httpx.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=settings.NORMALIZE_LLM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            response_text = payload.get("message", {}).get("content", "").strip()
            data = json.loads(response_text)
            if isinstance(data, dict) and isinstance(data.get(field), dict):
                data = data[field]
            converted = _convert_llm_limit(field, data, context, model_name)
            if complex_payload is not None:
                # 규칙 단계에서 복합 가능성이 확인된 필드는 모델이 direct라고
                # 잘못 분류해도 단일 컬럼으로 평탄화하지 않는다.
                fallback_res[field] = (
                    converted
                    if converted and converted.get("requires_manual_review")
                    else complex_payload
                )
            else:
                fallback_res[field] = converted
            if fallback_res[field] is None:
                print(f"  [Ollama Structure] 검증에서 거절된 응답: {response_text[:500]}", flush=True)
        except Exception as exc:
            fallback_res[field] = complex_payload
            print(f"  [Ollama Structure] {field} 추출 실패: {exc}", flush=True)
    return fallback_res
