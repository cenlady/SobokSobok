import json

from app.services.policy_ingest import crawl_sbiz24_once


def main() -> None:
    stats = crawl_sbiz24_once()
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
