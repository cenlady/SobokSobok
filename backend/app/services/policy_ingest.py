from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.crawlers.sbiz24_client import Sbiz24Client
from app.models.policy import PolicyAnnouncement, PolicyAttachment


def crawl_sbiz24_once() -> dict[str, int | bool]:
    db = SessionLocal()
    locked = False
    stats: dict[str, int | bool] = {
        "locked": False,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "attachments_created": 0,
        "attachments_skipped": 0,
        "errors": 0,
    }

    try:
        # 여러 crawler 컨테이너가 동시에 떠도 한 프로세스만 수집하도록 막는다.
        locked = _try_advisory_lock(db)
        stats["locked"] = locked
        if not locked:
            return stats

        with Sbiz24Client() as client:
            # 현재 조건에 맞는 목록은 매번 전체 조회하고, DB 저장 시 중복을 거른다.
            announcements = client.fetch_announcements(page_size=settings.SBIZ24_PAGE_SIZE)
            stats["fetched"] = len(announcements)

            for row, raw_list_json in announcements:
                try:
                    item_stats = _ingest_row(db, client, row, raw_list_json)
                    for key, value in item_stats.items():
                        stats[key] = int(stats[key]) + value
                except Exception as exc:
                    db.rollback()
                    stats["errors"] = int(stats["errors"]) + 1
                    print(f"[sbiz24-crawler] row failed: {exc}", flush=True)

                if settings.SBIZ24_REQUEST_DELAY_SECONDS > 0:
                    time.sleep(settings.SBIZ24_REQUEST_DELAY_SECONDS)

        return stats
    finally:
        if locked:
            _release_advisory_lock(db)
        db.close()


def _ingest_row(
    db: Session,
    client: Sbiz24Client,
    row: dict[str, Any],
    raw_list_json: dict[str, Any],
) -> dict[str, int]:
    stats = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "attachments_created": 0,
        "attachments_skipped": 0,
    }

    pbanc_sn = _as_int(_pick(row, "pbancSn", "pbanc_sn"))
    if pbanc_sn is None:
        raise ValueError(f"Missing pbancSn: {row}")

    # 목록 응답에는 본문/기간 정보가 부족할 수 있어 공고별 상세 API를 한 번 더 조회한다.
    raw_detail_json = client.fetch_detail(pbanc_sn)
    detail = _extract_default(raw_detail_json)
    if not isinstance(detail, dict):
        detail = {}

    title = _pick(detail, "pbancNm", "title") or _pick(row, "pbancNm", "title") or f"공고 {pbanc_sn}"
    target = _pick(detail, "rcrtTypeCdNm", "rcrtTypeCdNmListDisplay") or _pick(
        row,
        "rcrtTypeCdNm",
        "rcrtTypeCdNmListDisplay",
    )
    category = _pick(row, "bizTypeNm", "bizType", "sprtBizTypeNm") or _pick(
        detail,
        "bizTypeNm",
        "sprtBizTypeNm",
    )
    organization = _pick(
        detail,
        "jrsdInstNm",
        "departNm",
        "insttNm",
    ) or _pick(row, "jrsdInstNm", "departNm", "insttNm")
    status = _pick(row, "aplyPsbltySeNm", "aplySeNm", "status") or "신청가능"
    content_html = _pick(detail, "pbancDtlCn", "dtlCn", "content") or ""
    content_text = _html_to_text(content_html)

    rcpt_period = detail.get("rcptPd") if isinstance(detail.get("rcptPd"), dict) else {}
    apply_start = rcpt_period.get("from") or _pick(row, "aplyBgngDt", "reqstBeginDe")
    apply_end = rcpt_period.get("to") or _pick(row, "aplyEndDt", "reqstEndDe")

    content_hash = _make_content_hash(
        {
            "title": title,
            "target": target,
            "category": category,
            "organization": organization,
            "apply_start": apply_start,
            "apply_end": apply_end,
            "status": status,
            "content_text": content_text,
        }
    )

    now = datetime.now(timezone.utc)
    # pbanc_sn이 공고의 고유 키라서, 이미 있으면 새 row를 만들지 않고 갱신한다.
    existing = db.get(PolicyAnnouncement, pbanc_sn)

    if existing is None:
        existing = PolicyAnnouncement(
            pbanc_sn=pbanc_sn,
            source="sbiz24",
            title=title,
            target=target,
            category=category,
            organization=organization,
            apply_start=apply_start,
            apply_end=apply_end,
            status=status,
            detail_url=f"https://www.sbiz24.kr/#/pbanc/{pbanc_sn}",
            content_html=content_html,
            content_text=content_text,
            raw_list_json=raw_list_json,
            raw_detail_json=raw_detail_json,
            content_hash=content_hash,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
        )
        db.add(existing)
        stats["created"] += 1
    else:
        # 내용 해시가 같으면 중복 저장 없이 unchanged로 집계한다.
        if existing.content_hash == content_hash:
            stats["unchanged"] += 1
        else:
            stats["updated"] += 1

        existing.title = title
        existing.target = target
        existing.category = category
        existing.organization = organization
        existing.apply_start = apply_start
        existing.apply_end = apply_end
        existing.status = status
        existing.detail_url = f"https://www.sbiz24.kr/#/pbanc/{pbanc_sn}"
        existing.content_html = content_html
        existing.content_text = content_text
        existing.raw_list_json = raw_list_json
        existing.raw_detail_json = raw_detail_json
        existing.content_hash = content_hash
        existing.last_seen_at = now
        existing.is_active = True

    db.flush()
    file_stats = _ingest_attachments(db, client, pbanc_sn)
    stats["attachments_created"] += file_stats["created"]
    stats["attachments_skipped"] += file_stats["skipped"]
    db.commit()

    return stats


def _ingest_attachments(db: Session, client: Sbiz24Client, pbanc_sn: int) -> dict[str, int]:
    stats = {"created": 0, "skipped": 0}
    raw_files_json = client.fetch_attachment_metadata(pbanc_sn)
    files = _extract_default(raw_files_json)
    if not isinstance(files, list):
        return stats

    for file_item in files:
        file_id = _pick(file_item, "fileId")
        file_name = _pick(file_item, "fileNm", "fileName")
        if not file_id or not file_name:
            continue

        # file_id가 첨부파일 고유 키라서 이미 저장된 파일은 재다운로드하지 않는다.
        existing = db.get(PolicyAttachment, file_id)
        if existing is not None:
            stats["skipped"] += 1
            continue

        file_bytes = client.download_attachment(file_id)
        saved_path = _save_attachment(pbanc_sn, file_name, file_bytes)
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = _as_int(_pick(file_item, "fileSz", "fileSize")) or len(file_bytes)

        db.add(
            PolicyAttachment(
                file_id=file_id,
                pbanc_sn=pbanc_sn,
                file_name=file_name,
                file_size=file_size,
                saved_path=str(saved_path),
                file_hash=file_hash,
                raw_file_json=file_item,
                downloaded_at=datetime.now(timezone.utc),
            )
        )
        stats["created"] += 1

    return stats


def _save_attachment(pbanc_sn: int, file_name: str, file_bytes: bytes) -> Path:
    base_dir = Path(settings.ATTACHMENT_DIR)
    # DB에는 파일 bytes를 넣지 않고, 공고 번호별 폴더 경로와 해시만 저장한다.
    target_dir = base_dir / str(pbanc_sn)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_file_name = _safe_file_name(file_name)
    target_path = target_dir / safe_file_name
    target_path.write_bytes(file_bytes)
    return target_path


def _try_advisory_lock(db: Session) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": settings.CRAWLER_ADVISORY_LOCK_ID},
        ).scalar()
    )


def _release_advisory_lock(db: Session) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": settings.CRAWLER_ADVISORY_LOCK_ID},
    )
    db.commit()


def _extract_default(response_json: dict[str, Any]) -> Any:
    data = response_json.get("data") or {}
    if isinstance(data, dict) and "list" in data:
        return data["list"]
    default = data.get("default") if isinstance(data, dict) else None
    if isinstance(default, dict) and "list" in default:
        return default["list"]
    if isinstance(data, dict) and "default" in data:
        return data["default"]
    return data


def _pick(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _html_to_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _make_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_file_name(file_name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "_", file_name).strip()
    return safe or "attachment"
