import json

from app.services.gov24_ingest import crawl_gov24_once


def main() -> None:
    stats = crawl_gov24_once()
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
