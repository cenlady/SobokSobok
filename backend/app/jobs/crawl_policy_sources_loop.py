import json
import time
import traceback

from app.core.config import settings
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
        try:
            stats = normalize_policy_sources_once()
            print(
                "[normalizer] success "
                + json.dumps(stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print("[normalizer] failed", flush=True)
            traceback.print_exc()

    if settings.EXTRACT_AFTER_NORMALIZE:
        try:
            stats = extract_pending_attachments_once()
            print(
                "[extractor] success "
                + json.dumps(stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print("[extractor] failed", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
