from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.crawlers.semas_client import SemasClient, SemasProgramPage
from app.models.policy import PolicyProgramPage


def crawl_semas_program_pages_once() -> dict[str, int | bool]:
    db = SessionLocal()
    locked = False
    stats: dict[str, int | bool] = {
        "locked": False,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "deactivated": 0,
        "errors": 0,
    }

    try:
        # Sbiz24와 별도 lock을 써서 SEMAS 수집 중복 실행만 막는다.
        locked = _try_advisory_lock(db, settings.SEMAS_CRAWLER_ADVISORY_LOCK_ID)
        stats["locked"] = locked
        if not locked:
            return stats

        seen_urls: set[str] = set()
        with SemasClient() as client:
            links = client.fetch_program_links(settings.SEMAS_SEED_URL)
            stats["fetched"] = len(links)

            for link in links:
                try:
                    page = client.fetch_program_page(link.url)
                    item_stats = _ingest_page(db, page)
                    seen_urls.add(page.source_url)
                    for key, value in item_stats.items():
                        stats[key] = int(stats[key]) + value
                except Exception as exc:
                    db.rollback()
                    stats["errors"] = int(stats["errors"]) + 1
                    print(f"[semas-crawler] page failed url={link.url}: {exc}", flush=True)

                if settings.SEMAS_REQUEST_DELAY_SECONDS > 0:
                    time.sleep(settings.SEMAS_REQUEST_DELAY_SECONDS)

        stats["deactivated"] = _deactivate_missing_pages(db, seen_urls)
        db.commit()
        return stats
    finally:
        if locked:
            _release_advisory_lock(db, settings.SEMAS_CRAWLER_ADVISORY_LOCK_ID)
        db.close()


def _ingest_page(db: Session, page: SemasProgramPage) -> dict[str, int]:
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    content_hash = _make_content_hash(
        {
            "category": page.category,
            "program_name": page.program_name,
            "content_text": page.content_text,
            "sections": page.sections,
            "breadcrumbs": page.breadcrumbs,
        }
    )
    now = datetime.now(timezone.utc)
    existing = (
        db.query(PolicyProgramPage)
        .filter(PolicyProgramPage.source_url == page.source_url)
        .one_or_none()
    )

    if existing is None:
        db.add(
            PolicyProgramPage(
                source="semas",
                source_url=page.source_url,
                category=page.category,
                program_name=page.program_name,
                content_html=page.content_html,
                content_text=page.content_text,
                sections_json=page.sections,
                raw_breadcrumbs_json=page.breadcrumbs,
                content_hash=content_hash,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
        )
        stats["created"] += 1
    else:
        # source_url이 고유 키 역할을 하므로 같은 페이지는 새 row로 쌓지 않는다.
        if existing.content_hash == content_hash:
            stats["unchanged"] += 1
        else:
            stats["updated"] += 1

        existing.category = page.category
        existing.program_name = page.program_name
        existing.content_html = page.content_html
        existing.content_text = page.content_text
        existing.sections_json = page.sections
        existing.raw_breadcrumbs_json = page.breadcrumbs
        existing.content_hash = content_hash
        existing.last_seen_at = now
        existing.is_active = True

    db.commit()
    return stats


def _deactivate_missing_pages(db: Session, seen_urls: set[str]) -> int:
    if not seen_urls:
        return 0

    stale_pages = (
        db.query(PolicyProgramPage)
        .filter(PolicyProgramPage.source == "semas")
        .filter(PolicyProgramPage.is_active.is_(True))
        .filter(PolicyProgramPage.source_url.notin_(seen_urls))
        .all()
    )
    for page in stale_pages:
        page.is_active = False
        page.last_seen_at = datetime.now(timezone.utc)
    return len(stale_pages)


def _try_advisory_lock(db: Session, lock_id: int) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id}).scalar())


def _release_advisory_lock(db: Session, lock_id: int) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
    db.commit()


def _make_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
