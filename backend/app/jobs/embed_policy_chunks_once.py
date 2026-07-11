import argparse
import json
import uuid

from app.core.database import SessionLocal
from app.services.chat_rag import build_policy_chunks, get_policy_chunk_stats, is_langsmith_enabled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="policy_documents를 챗봇 RAG용 policy_chunks로 청킹하고 임베딩합니다."
    )
    parser.add_argument("--policy-id", type=str, default=None, help="특정 normalized_policies.id만 처리")
    parser.add_argument("--limit", type=int, default=None, help="처리할 policy_documents 수 제한")
    parser.add_argument("--no-force", action="store_true", help="이미 청크가 있는 문서는 건너뜀")
    parser.add_argument("--provider", type=str, default=None, help="openai | gemini | ollama")
    parser.add_argument("--model", type=str, default=None, help="임베딩 모델명")
    parser.add_argument("--chunk-size", type=int, default=None, help="기본 280자")
    parser.add_argument("--chunk-overlap", type=int, default=None, help="기본 40자")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    policy_id = uuid.UUID(args.policy_id) if args.policy_id else None

    db = SessionLocal()
    try:
        before = get_policy_chunk_stats(db)
        result = build_policy_chunks(
            db=db,
            policy_id=policy_id,
            limit=args.limit,
            force=not args.no_force,
            provider=args.provider,
            model_name=args.model,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        after = get_policy_chunk_stats(db)
        print(
            json.dumps(
                {
                    "before": before,
                    "result": result,
                    "after": after,
                    "langsmith_enabled": is_langsmith_enabled(),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
