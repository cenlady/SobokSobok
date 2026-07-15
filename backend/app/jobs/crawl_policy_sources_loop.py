import json
import time
import traceback

from app.core.config import settings
from app.core.database import SessionLocal
from app.jobs.build_prep_vectors_once import build_prep_vectors_once
from app.jobs.build_rec_vectors_once import build_rec_vectors_once
from app.services.build_review_vectors import build_review_vectors_once
from app.services.chat_rag import build_policy_chunks
from app.services.extract_attachments import extract_pending_attachments_once
from app.services.gov24_ingest import crawl_gov24_once
from app.services.normalize_policies import normalize_policy_sources_once
from app.services.policy_ingest import crawl_sbiz24_once
from app.services.semas_ingest import crawl_semas_program_pages_once


def main() -> None:
    interval = settings.CRAWL_INTERVAL_SECONDS
    print(f"[crawler] starting loop interval={interval}s", flush=True)

    while True:
        started = time.time()
        # 컨테이너가 켜지면 즉시 1회 실행하고, 이후 설정한 주기마다 반복한다.
        _run_all_jobs()

        elapsed = time.time() - started
        sleep_for = max(interval - elapsed, 0)
        print(f"[crawler] sleeping {sleep_for:.1f}s", flush=True)
        time.sleep(sleep_for)


def _run_all_jobs() -> None:
    jobs = [
        ("sbiz24", crawl_sbiz24_once),
        ("semas", crawl_semas_program_pages_once),
    ]
    if settings.GOV24_SERVICE_KEY:
        jobs.append(("gov24", crawl_gov24_once))
    for name, job in jobs:
        try:
            stats = job()
            print(
                f"[{name}-crawler] success "
                + json.dumps(stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print(f"[{name}-crawler] failed", flush=True)
            traceback.print_exc()

    if settings.NORMALIZE_AFTER_CRAWL:
        _run_normalization("normalizer")

    extraction_stats: dict | None = None
    if settings.EXTRACT_AFTER_NORMALIZE:
        try:
            extraction_stats = extract_pending_attachments_once()
            print(
                "[extractor] success "
                + json.dumps(extraction_stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print("[extractor] failed", flush=True)
            traceback.print_exc()

    # 첫 정규화가 첨부 링크를 만든 뒤 추출기가 본문을 채우므로, 성공한 첨부가
    # 있으면 임베딩 전에 한 번 더 정규화해야 같은 수집 주기에 반영된다.
    if settings.NORMALIZE_AFTER_CRAWL and _needs_post_extraction_refresh(extraction_stats):
        _run_normalization("post-extraction-normalizer")

    if settings.EMBED_CHAT_CHUNKS_AFTER_NORMALIZE:
        try:
            stats = _build_missing_chat_chunks_once()
            print(
                "[chat-rag-embedding] success "
                + json.dumps(stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print("[chat-rag-embedding] failed", flush=True)
            traceback.print_exc()

    try:
        stats = build_rec_vectors_once()
        print(
            "[embedding] success "
            + json.dumps(stats, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
    except Exception:
        print("[embedding] failed", flush=True)
        traceback.print_exc()

    try:
        stats = build_review_vectors_once()
        print(
            "[review-embedding] success "
            + json.dumps(stats, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
    except Exception:
        print("[review-embedding] failed", flush=True)
        traceback.print_exc()

    try:
        stats = build_prep_vectors_once()
        print(
            "[prep-embedding] success "
            + json.dumps(stats, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
    except Exception:
        print("[prep-embedding] failed", flush=True)
        traceback.print_exc()


def _build_missing_chat_chunks_once() -> dict:
    db = SessionLocal()
    try:
        return build_policy_chunks(db=db, force=False)
    finally:
        db.close()


def _needs_post_extraction_refresh(stats: dict | None) -> bool:
    return bool(stats and int(stats.get("success", 0)) > 0)


def _run_normalization(label: str) -> dict | None:
    try:
        stats = normalize_policy_sources_once()
        result_label = "failed" if int(stats.get("errors", 0)) > 0 else "success"
        print(
            f"[{label}] {result_label} "
            + json.dumps(stats, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
        return stats
    except Exception:
        print(f"[{label}] failed", flush=True)
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
