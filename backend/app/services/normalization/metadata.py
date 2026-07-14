from __future__ import annotations

import calendar
import hashlib
import re
from datetime import datetime
from typing import Any

from app.models.gov24 import Gov24SupportCondition
from app.core.time import korea_now_naive
from app.services.normalization.common import (
    _as_int_text,
    _as_text,
    _clean_text,
    _first_text,
    _join_text,
    _make_hash,
    _merge_unique_lists,
)
from app.services.normalization.documents import (
    _document_name_key,
    _extract_required_document_llm_candidates,
    _extract_required_documents,
    _extract_required_documents_from_attachment,
    _first_section_text_by_type,
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
from app.services.normalization.llm_documents import (
    _resolve_required_documents_with_llm_cache,
)
from app.services.normalization.llm_limits import _resolve_limits_with_llm_cache
from app.services.normalization.regions import _extract_region_metadata

INDUSTRY_KEYWORDS = {
    "restaurant": ("음식점", "외식업", "식당", "요식업", "식품업", "카페", "베이커리"),
    "manufacturing": ("제조", "소공인", "공장", "생산", "스마트제조"),
    "retail": ("유통업", "도매업", "소매업", "도소매", "판매업", "슈퍼", "소매점"),
    "tourism": ("관광업", "숙박업", "호텔", "여행업"),
    "market": ("전통시장", "상점가", "골목상권", "상권"),
    "export": ("수출", "해외", "글로벌", "FTA"),
    "digital": ("디지털산업", "소프트웨어업", "AI기업", "온라인판매업"),
    "agriculture_fishery_forestry": ("농업", "어업", "수산업", "임업", "축산업"),
    "information_communication": ("정보통신업", "ICT기업", "IT기업"),
}

BUSINESS_STATUS_KEYWORDS = {
    # `small_business`는 화면과 추천 엔진에서 "소상공인"을 뜻한다.
    # "중소기업" 안에도 "소기업" 문자열이 들어 있고 "영세"도 대상 규모를
    # 확정하지 못하므로, 두 표현을 여기서 매칭하면 일반 중소기업 정책이
    # 소상공인 정책으로 승격된다. 실제 소상공인 명시만 보수적으로 사용한다.
    "small_business": ("소상공인",),
    "small_manufacturer": ("소공인", "도시형소공인"),
    "pre_founder": ("예비창업", "예비 창업", "창업예정", "창업 예정", "예비창업자"),
    "operating_business": ("기존사업자", "사업자", "영업중", "정상영업", "운영 중", "운영중"),
    "closing_business": ("폐업", "폐업예정", "폐업 예정", "재기", "희망리턴"),
    "traditional_market": ("전통시장", "상인회", "상점가"),
}

GOV24_INDUSTRY_TAGS = {
    "restaurant",
    "manufacturing",
    "other_business",
    "agriculture_fishery_forestry",
    "information_communication",
    "company_other_business",
}
GOV24_LIFECYCLE_TAGS = {"pre_founder", "operating_business", "closing_business"}


def _source_metadata(
    *,
    source: str,
    source_hash: str,
    existing_llm_cache: dict[str, Any] | None,
    title: str | None,
    category: str | None,
    target_text: str | None,
    content_text: str | None,
    sections: list[dict[str, str | None]],
    extra_texts: list[Any] | None = None,
    default_business_status_tags: list[str] | None = None,
    region_text: str | None = None,
    region_fallback_text: str | None = None,
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
    industry_condition = _extract_industry_condition(eligibility_text, INDUSTRY_KEYWORDS)
    industry_tags = industry_condition["include_tags"]
    required_documents = _extract_required_documents(sections, source)
    label = _first_text(title, source) or source

    if attachment_texts:
        for att_text in attachment_texts:
            required_documents = _merge_unique_document_items(
                required_documents,
                _extract_required_documents_from_attachment(att_text, source),
            )

    document_candidates = _extract_required_document_llm_candidates(
        sections,
        attachment_texts,
    )
    llm_documents, document_llm_cache = _resolve_required_documents_with_llm_cache(
        document_candidates,
        source=source,
        source_hash=source_hash,
        existing_llm_cache=existing_llm_cache,
        log_label=f"{source} '{label[:30]}'",
    )
    required_documents = _merge_unique_document_items(required_documents, llm_documents)

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

    parsed_limits = {
        "employee_limit": _extract_employee_limit(eligibility_text),
        "sales_limit": _extract_sales_limit(eligibility_text),
        "business_age_limit": _extract_business_age_limit(eligibility_text),
    }
    limits, limit_llm_cache = _resolve_limits_with_llm_cache(
        eligibility_text,
        parsed_limits,
        source_hash=source_hash,
        existing_llm_cache=existing_llm_cache,
        log_label=f"{source} '{label[:30]}'",
    )
    llm_cache = {**document_llm_cache, **limit_llm_cache}

    return {
        "region": _extract_region_metadata(
            region_text if region_text is not None else eligibility_text,
            fallback_text=region_fallback_text,
        ),
        "summary_text": _first_section_text_by_type(sections, "summary"),
        "target_text": target_val,
        "support_content_text": _first_section_text_by_type(sections, "support_content"),
        "required_documents": required_documents,
        "business_status_tags": business_status_tags,
        "industry_tags": industry_tags,
        "industry_condition": industry_condition,
        "employee_limit": limits["employee_limit"],
        "sales_limit": limits["sales_limit"],
        "business_age_limit": limits["business_age_limit"],
        "money_conditions": _extract_money_conditions(text_blob),
        "application_methods": _extract_application_methods(application_text or text_blob),
        "contacts": _extract_contacts(_join_text([contacts_text, text_blob])),
        "llm_cache": llm_cache,
    }


def _merge_unique_document_items(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    values = list(existing)
    seen = {_document_name_key(item.get("name")) for item in values}
    for item in incoming:
        name = _clean_text(item.get("name"))
        key = _document_name_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        values.append(item)
    return values


def _merge_industry_condition_with_codes(
    text_condition: dict[str, Any],
    coded_tags: list[str],
) -> dict[str, Any]:
    if not coded_tags:
        return text_condition

    coded_set = set(coded_tags)
    if GOV24_INDUSTRY_TAGS.issubset(coded_set):
        # Gov24가 업종 선택지를 전부 Y로 내려주는 서비스는 특정 업종 제한이
        # 아니라 모든 업종에 열려 있다는 뜻이다. 다만 지원대상 원문에서 별도
        # 업종 제한을 찾았다면 그 텍스트 근거를 우선한다.
        if text_condition.get("mode") in {"restricted", "unrestricted"}:
            return text_condition
        return {
            "mode": "unrestricted",
            "include_tags": [],
            "exclude_tags": [],
            "confidence": 0.98,
            "extraction_method": "gov24_all_industry_codes_unrestricted",
            "evidence": [
                {
                    "disposition": "unrestricted",
                    "source_text": "gov24_all_industry_codes",
                }
            ],
        }

    include_tags = _merge_unique_lists(coded_tags, text_condition.get("include_tags") or [])
    evidence = [
        {
            "tag": tag,
            "disposition": "include",
            "source_text": "gov24_support_condition_code",
        }
        for tag in coded_tags
    ]
    evidence.extend(text_condition.get("evidence") or [])
    return {
        "mode": "restricted",
        "include_tags": include_tags,
        "exclude_tags": text_condition.get("exclude_tags") or [],
        "confidence": 0.98,
        "extraction_method": "gov24_condition_code_and_context_rule",
        "evidence": evidence,
    }


def _merge_gov24_business_status_tags(
    coded_tags: list[str],
    text_tags: list[str],
    user_type: str | None,
) -> list[str]:
    coded = set(coded_tags)
    tokens = {token.strip() for token in (user_type or "").split("||") if token.strip()}
    broad_user_type = len(tokens) >= 3 and "소상공인" in tokens

    if GOV24_LIFECYCLE_TAGS.issubset(coded):
        coded -= GOV24_LIFECYCLE_TAGS
    if broad_user_type:
        coded.discard("small_medium_business")

    merged = _merge_unique_lists(sorted(coded), text_tags)
    if not broad_user_type and "소상공인" in tokens and "small_business" not in merged:
        merged.append("small_business")
    return merged


def _gov24_audience_specificity(user_type: str | None, target_text: str | None) -> str:
    target = _clean_text(target_text) or ""
    tokens = {token.strip() for token in (user_type or "").split("||") if token.strip()}

    if "소상공인" in target:
        return "direct_small_business"
    if tokens == {"소상공인"}:
        return "direct_small_business"
    if len(tokens) >= 3 and "소상공인" in tokens:
        return "broad_public"
    if "소상공인" in tokens or any(term in target for term in ("자영업자", "사업자", "중소기업")):
        return "related_business"
    return "broad_public"


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
    now = korea_now_naive()
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
