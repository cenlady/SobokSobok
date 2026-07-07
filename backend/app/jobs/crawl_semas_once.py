import json

from app.services.semas_ingest import crawl_semas_program_pages_once


def main() -> None:
    stats = crawl_semas_program_pages_once()
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
