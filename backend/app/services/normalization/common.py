from __future__ import annotations

import hashlib
import json
import re
from typing import Any

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
