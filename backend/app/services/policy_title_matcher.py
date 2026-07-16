import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Dict, Literal, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.normalized_policy import NormalizedPolicy


TITLE_INDEX_TTL_SECONDS = 300.0
MIN_FULL_TITLE_LENGTH = 4
MIN_ALIAS_LENGTH = 6
GENERIC_TITLE_FORMS = {
    "공고",
    "모집공고",
    "지원",
    "지원사업",
    "정책지원",
    "소상공인지원",
}


@dataclass(frozen=True)
class PolicyTitleForm:
    text: str
    priority: int
    match_type: Literal["full", "admin_clean", "prefix", "no_year", "core"]


@dataclass(frozen=True)
class PolicyTitleEntry:
    policy_id: uuid.UUID
    title: str
    duplicate_group_key: str
    summary: Optional[str]
    support_type: Optional[str]
    apply_end: Optional[datetime]
    status: Optional[str]
    updated_at: Optional[datetime]
    forms: Tuple[PolicyTitleForm, ...]


@dataclass(frozen=True)
class PolicyTitleResolution:
    status: Literal["none", "matched", "ambiguous"]
    policy_id: Optional[uuid.UUID] = None
    match_type: Optional[str] = None
    candidates: Tuple[Dict[str, Any], ...] = ()


_TITLE_INDEX_CACHE: Dict[str, Tuple[float, Tuple[PolicyTitleEntry, ...]]] = {}
_TITLE_INDEX_LOCK = RLock()


def normalize_policy_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _remove_admin_markers(value: str) -> str:
    return re.sub(r"\((?:수정|변경|정정|재공고|추가모집|연장)\)", "", value or "").strip()


def _remove_leading_year(value: str) -> str:
    return re.sub(r"^\s*\[?\s*20\d{2}\s*년(?:도)?\s*\]?\s*", "", value or "").strip()


def _remove_trailing_admin_suffix(value: str) -> str:
    cleaned = (value or "").strip()
    suffix_patterns = (
        r"\s*(?:모집\s*)?공고\s*$",
        r"\s*(?:융자|시행|사업)\s*계획\s*$",
        r"\s*(?:지원\s*)?사업\s*$",
    )
    changed = True
    while changed and cleaned:
        changed = False
        for pattern in suffix_patterns:
            updated = re.sub(pattern, "", cleaned).strip()
            if updated != cleaned:
                cleaned = updated
                changed = True
                break
    return cleaned


def _add_form(
    forms: Dict[str, PolicyTitleForm],
    value: str,
    *,
    priority: int,
    match_type: Literal["full", "admin_clean", "prefix", "no_year", "core"],
) -> None:
    normalized = normalize_policy_title(value)
    minimum_length = MIN_FULL_TITLE_LENGTH if match_type == "full" else MIN_ALIAS_LENGTH
    if len(normalized) < minimum_length or normalized in GENERIC_TITLE_FORMS:
        return

    existing = forms.get(normalized)
    if existing is None or priority > existing.priority:
        forms[normalized] = PolicyTitleForm(
            text=normalized,
            priority=priority,
            match_type=match_type,
        )


def build_policy_title_forms(title: str) -> Tuple[PolicyTitleForm, ...]:
    """공식 제목의 공백·연도·행정 표기를 흡수한 안전한 직접 매칭용 형태를 만든다."""
    forms: Dict[str, PolicyTitleForm] = {}
    full = (title or "").strip()
    admin_clean = _remove_admin_markers(full)
    prefix = admin_clean.split("(", maxsplit=1)[0].strip()

    _add_form(forms, full, priority=4, match_type="full")
    _add_form(forms, admin_clean, priority=4, match_type="admin_clean")
    _add_form(forms, prefix, priority=3, match_type="prefix")

    aliases = (full, admin_clean, prefix)
    for alias in aliases:
        _add_form(
            forms,
            _remove_leading_year(alias),
            priority=3,
            match_type="no_year",
        )
        _add_form(
            forms,
            _remove_trailing_admin_suffix(alias),
            priority=2,
            match_type="core",
        )
        _add_form(
            forms,
            _remove_trailing_admin_suffix(_remove_leading_year(alias)),
            priority=2,
            match_type="core",
        )

    return tuple(sorted(forms.values(), key=lambda form: (-form.priority, -len(form.text), form.text)))


def _database_key(db: Session) -> str:
    try:
        bind = db.get_bind()
        url = bind.url.render_as_string(hide_password=True)
        return str(url)
    except Exception:
        return f"session:{id(db)}"


def clear_policy_title_index_cache() -> None:
    with _TITLE_INDEX_LOCK:
        _TITLE_INDEX_CACHE.clear()


def load_policy_title_index(db: Session) -> Tuple[PolicyTitleEntry, ...]:
    cache_key = _database_key(db)
    now = time.monotonic()
    with _TITLE_INDEX_LOCK:
        cached = _TITLE_INDEX_CACHE.get(cache_key)
        if cached is not None and cached[0] > now:
            return cached[1]

    rows = (
        db.query(
            NormalizedPolicy.id,
            NormalizedPolicy.title,
            NormalizedPolicy.duplicate_group_key,
            NormalizedPolicy.summary,
            NormalizedPolicy.support_type,
            NormalizedPolicy.apply_end,
            NormalizedPolicy.status,
            NormalizedPolicy.updated_at,
        )
        .filter(NormalizedPolicy.is_active.is_(True))
        .all()
    )
    entries_list = []
    for row in rows:
        forms = build_policy_title_forms(row.title)
        if not forms:
            continue
        entries_list.append(
            PolicyTitleEntry(
                policy_id=row.id,
                title=row.title,
                duplicate_group_key=row.duplicate_group_key,
                summary=row.summary,
                support_type=row.support_type,
                apply_end=row.apply_end,
                status=row.status,
                updated_at=row.updated_at,
                forms=forms,
            )
        )
    entries = tuple(entries_list)
    with _TITLE_INDEX_LOCK:
        _TITLE_INDEX_CACHE[cache_key] = (now + TITLE_INDEX_TTL_SECONDS, entries)
    return entries


def _entry_sort_key(entry: PolicyTitleEntry) -> Tuple[int, float, str]:
    status_rank = 1 if (entry.status or "").lower() == "open" else 0
    updated_at = entry.updated_at.timestamp() if entry.updated_at else 0.0
    return status_rank, updated_at, entry.title


def _candidate(entry: PolicyTitleEntry, *, score: float) -> Dict[str, Any]:
    return {
        "policy_id": str(entry.policy_id),
        "title": entry.title,
        "summary": entry.summary,
        "support_type": entry.support_type,
        "apply_end": entry.apply_end.isoformat() if entry.apply_end else None,
        "score": score,
        "source_count": 1,
    }


def resolve_policy_title(
    query: str,
    entries: Tuple[PolicyTitleEntry, ...],
) -> PolicyTitleResolution:
    """질문 안에 포함된 정책 제목을 찾아 단일 정책·복수 후보·미일치를 구분한다."""
    normalized_query = normalize_policy_title(query)
    if len(normalized_query) < MIN_FULL_TITLE_LENGTH:
        return PolicyTitleResolution(status="none")

    matches: list[Tuple[PolicyTitleEntry, PolicyTitleForm]] = []
    for entry in entries:
        matched_forms = [form for form in entry.forms if form.text in normalized_query]
        if not matched_forms:
            continue
        best_form = max(matched_forms, key=lambda form: (form.priority, len(form.text)))
        matches.append((entry, best_form))

    if not matches:
        return PolicyTitleResolution(status="none")

    best_priority = max(form.priority for _, form in matches)
    priority_matches = [(entry, form) for entry, form in matches if form.priority == best_priority]
    best_length = max(len(form.text) for _, form in priority_matches)
    top_matches = [
        (entry, form)
        for entry, form in priority_matches
        if len(form.text) == best_length
    ]

    grouped: Dict[str, list[Tuple[PolicyTitleEntry, PolicyTitleForm]]] = {}
    for entry, form in top_matches:
        grouped.setdefault(entry.duplicate_group_key or str(entry.policy_id), []).append((entry, form))

    score_by_priority = {4: 1.0, 3: 0.95, 2: 0.9}
    score = score_by_priority[best_priority]
    representatives = [
        max(group, key=lambda item: _entry_sort_key(item[0]))
        for group in grouped.values()
    ]
    representatives.sort(key=lambda item: _entry_sort_key(item[0]), reverse=True)

    if len(representatives) == 1:
        entry, form = representatives[0]
        return PolicyTitleResolution(
            status="matched",
            policy_id=entry.policy_id,
            match_type=form.match_type,
        )

    return PolicyTitleResolution(
        status="ambiguous",
        candidates=tuple(_candidate(entry, score=score) for entry, _ in representatives[:3]),
    )


def resolve_policy_title_from_db(db: Session, query: str) -> PolicyTitleResolution:
    return resolve_policy_title(query, load_policy_title_index(db))
