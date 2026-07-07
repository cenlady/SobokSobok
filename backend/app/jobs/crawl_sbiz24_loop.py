import json
import time
import traceback

from app.core.config import settings
from app.services.policy_ingest import crawl_sbiz24_once


def main() -> None:
    interval = settings.CRAWL_INTERVAL_SECONDS
    print(f"[sbiz24-crawler] starting loop interval={interval}s", flush=True)

    while True:
        started = time.time()
        try:
            # 컨테이너가 켜지면 즉시 1회 실행하고, 이후 설정한 주기마다 반복한다.
            stats = crawl_sbiz24_once()
            print(
                "[sbiz24-crawler] success "
                + json.dumps(stats, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        except Exception:
            print("[sbiz24-crawler] failed", flush=True)
            traceback.print_exc()

        elapsed = time.time() - started
        sleep_for = max(interval - elapsed, 0)
        print(f"[sbiz24-crawler] sleeping {sleep_for:.1f}s", flush=True)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
