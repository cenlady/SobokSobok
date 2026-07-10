import json

from app.services.extract_attachments import extract_pending_attachments_once


def main() -> None:
    stats = extract_pending_attachments_once()
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
