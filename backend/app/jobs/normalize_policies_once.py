import json

from app.services.normalize_policies import normalize_policy_sources_once


def main() -> None:
    stats = normalize_policy_sources_once()
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
