import argparse
import json

from app.services.build_review_vectors import build_review_vectors_once


def main() -> None:
    parser = argparse.ArgumentParser(description="정책 요건을 임베딩해 review_vectors를 채운다")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="기존 벡터를 지우고 다시 생성 (임베딩 모델/차원 변경 시 사용)",
    )
    args = parser.parse_args()

    stats = build_review_vectors_once(rebuild=args.rebuild)
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
