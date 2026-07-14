# -*- coding: utf-8 -*-
"""[서류 검토 영역] 서류 발급 가이드를 prep_vectors에 적재한다.

prep_vectors 테이블은 진작 만들어져 있었지만 한 번도 채워진 적이 없다(0건).
서류 목록만 알려주고 "어디서 어떻게 떼는지"는 답하지 못하고 있었다.

멱등: 매번 전부 다시 쓴다. 가이드는 29개뿐이라 증분 갱신할 이유가 없고,
가이드 문구를 고쳤을 때 반영이 안 되는 편이 더 위험하다.

실행:
    docker compose exec api python -m app.jobs.build_prep_vectors_once
"""

from __future__ import annotations

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rag_utils import OllamaEmbeddingModel
from app.models.prep import PrepVector
from app.services.document_guides import GUIDES


def build_prep_vectors_once() -> dict[str, int]:
    db = SessionLocal()
    stats = {"guides": len(GUIDES), "written": 0}

    try:
        embedder = OllamaEmbeddingModel(
            model_name=settings.REVIEW_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

        texts = [guide.to_text() for guide in GUIDES]
        vectors = embedder.embed_documents(texts)

        # 전부 다시 쓴다. 가이드 문구를 고쳤는데 반영이 안 되는 게 더 위험하다.
        db.query(PrepVector).delete()

        for guide, text, vector in zip(GUIDES, texts, vectors):
            db.add(
                PrepVector(
                    document_name=guide.name,
                    guide_text=text,
                    embedding=vector,
                )
            )
            stats["written"] += 1

        db.commit()
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    result = build_prep_vectors_once()
    print(f"[prep-vectors] 가이드 {result['guides']}개 → {result['written']}건 적재", flush=True)
