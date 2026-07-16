"""정책명 직접 매칭과 기존 전역 벡터 검색 경로를 실제 DB에서 비교한다.

예시:
  PYTHONPATH=. python benchmarks/benchmark_policy_title_direct_match.py --limit 5 --model-mode local
"""

import argparse
import json
import statistics
import time
from typing import Any, Dict, List

from sqlalchemy import exists

from app.core.database import SessionLocal
from app.models.chat import PolicyChunk
from app.models.normalized_policy import NormalizedPolicy, PolicyDocument
from app.services.chat_rag import (
    retrieve_policy_chunk_sources,
    retrieve_policy_document_sources,
)
from app.services.policy_title_matcher import (
    clear_policy_title_index_cache,
    load_policy_title_index,
    resolve_policy_title,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정책명 직접 매칭 경로 벤치마크")
    parser.add_argument("--limit", type=int, default=5, help="비교할 정책 수")
    parser.add_argument("--model-mode", choices=("local", "cloud"), default="local")
    return parser.parse_args()


def _median(values: List[float]) -> float:
    return round(statistics.median(values), 2) if values else 0.0


def _select_cases(db, *, limit: int) -> List[Dict[str, Any]]:
    entries = load_policy_title_index(db)
    rows = (
        db.query(NormalizedPolicy.id, NormalizedPolicy.title)
        .filter(NormalizedPolicy.is_active.is_(True))
        .filter(exists().where(PolicyDocument.policy_id == NormalizedPolicy.id))
        .filter(exists().where(PolicyChunk.policy_id == NormalizedPolicy.id))
        .order_by(NormalizedPolicy.title.asc())
        .all()
    )
    cases: List[Dict[str, Any]] = []
    for row in rows:
        query = f"{row.title} 신청 기간 알려줘"
        match = resolve_policy_title(query, entries)
        if match.status != "matched" or match.policy_id != row.id:
            continue
        cases.append({"policy_id": row.id, "title": row.title, "query": query})
        if len(cases) >= limit:
            break
    return cases


def _is_direct_answer(response: Dict[str, Any], policy_id: str) -> bool:
    source_policy_ids = {str(source.get("policy_id")) for source in response.get("sources") or []}
    return response.get("response_mode") == "answer" and source_policy_ids == {policy_id}


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        clear_policy_title_index_cache()
        cases = _select_cases(db, limit=args.limit)
        if not cases:
            raise RuntimeError("직접 매칭 가능한 활성 정책 테스트 케이스를 찾지 못했습니다.")

        # 캐시가 준비된 API 프로세스의 일반 요청 상태를 측정한다.
        entries = load_policy_title_index(db)
        direct_latencies: List[float] = []
        baseline_latencies: List[float] = []
        direct_successes = 0
        baseline_successes = 0
        rows = []

        for case in cases:
            policy_id = str(case["policy_id"])

            direct_started = time.perf_counter()
            title_match = resolve_policy_title(case["query"], entries)
            direct_response = retrieve_policy_document_sources(
                db,
                case["query"],
                policy_id=title_match.policy_id,
            )
            direct_ms = (time.perf_counter() - direct_started) * 1000
            direct_ok = title_match.policy_id == case["policy_id"] and _is_direct_answer(
                direct_response,
                policy_id,
            )

            baseline_started = time.perf_counter()
            baseline_response = retrieve_policy_chunk_sources(
                db,
                case["query"],
                model_mode=args.model_mode,
            )
            baseline_ms = (time.perf_counter() - baseline_started) * 1000
            baseline_ok = _is_direct_answer(baseline_response, policy_id)

            direct_latencies.append(direct_ms)
            baseline_latencies.append(baseline_ms)
            direct_successes += int(direct_ok)
            baseline_successes += int(baseline_ok)
            rows.append(
                {
                    "title": case["title"],
                    "direct_match": {
                        "correct": direct_ok,
                        "latency_ms": round(direct_ms, 2),
                        "response_mode": direct_response.get("response_mode"),
                    },
                    "baseline_vector_search": {
                        "correct": baseline_ok,
                        "latency_ms": round(baseline_ms, 2),
                        "response_mode": baseline_response.get("response_mode"),
                    },
                }
            )

        print(
            json.dumps(
                {
                    "case_count": len(cases),
                    "model_mode": args.model_mode,
                    "direct_match": {
                        "correct_route_rate": round(direct_successes / len(cases), 4),
                        "median_latency_ms": _median(direct_latencies),
                        "embedding_calls_per_request": 0,
                    },
                    "baseline_vector_search": {
                        "correct_direct_answer_rate": round(baseline_successes / len(cases), 4),
                        "median_latency_ms": _median(baseline_latencies),
                        "embedding_calls_per_request": 1,
                    },
                    "cases": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
