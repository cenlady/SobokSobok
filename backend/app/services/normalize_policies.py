"""Orchestration entrypoint for policy normalization."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.normalized_policy import ensure_normalized_policy_schema
from app.services.normalization.sources import (
    _merge_stats,
    _normalize_gov24,
    _normalize_sbiz24,
    _normalize_semas,
)


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
