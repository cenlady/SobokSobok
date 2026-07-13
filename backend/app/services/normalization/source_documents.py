from __future__ import annotations

import json
import re
from typing import Any

from app.models.policy import PolicyAnnouncement, PolicyProgramPage
from app.services.normalization.common import _as_text, _clean_text, _join_text
from app.services.normalization.documents import (
    SECTION_TITLE_ALIASES,
    SECTION_TYPE_BY_TITLE,
    _document_type_for_title,
    _normalize_section_title,
)

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
