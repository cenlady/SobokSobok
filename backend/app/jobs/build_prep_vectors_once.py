# -*- coding: utf-8 -*-
"""[서류 검토 영역] 서류 발급 가이드를 prep_vectors에 적재한다.

prep_vectors 테이블은 진작 만들어져 있었지만 한 번도 채워진 적이 없다(0건).
서류 목록만 알려주고 "어디서 어떻게 떼는지"는 답하지 못하고 있었다.

멱등: 서류명·가이드 문구·모델·양쪽 벡터가 같으면 건너뛰고,
신규·변경·누락된 가이드만 임베딩한다.

실행:
    docker compose exec api python -m app.jobs.build_prep_vectors_once
"""

from __future__ import annotations

from app.core.database import SessionLocal
from app.core.model_provider import (
    get_embedding_model,
    resolve_embedding_model_spec_for_mode,
)
from app.models.prep import PrepVector
from app.services.document_guides import GUIDES, DocumentGuide


def build_prep_vectors_once() -> dict[str, int | str]:
    db = SessionLocal()
    stats: dict[str, int | str] = {
        "guides": len(GUIDES),
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "skipped": 0,
        "written": 0,
    }

    try:
        cloud_spec = resolve_embedding_model_spec_for_mode("prep", "cloud")
        local_spec = resolve_embedding_model_spec_for_mode("prep", "local")
        stats["cloud_model"] = cloud_spec.model
        stats["local_model"] = local_spec.model

        existing_by_name: dict[str, PrepVector] = {}
        for row in db.query(PrepVector).all():
            if row.document_name in existing_by_name:
                db.delete(row)
                stats["deleted"] = int(stats["deleted"]) + 1
            else:
                existing_by_name[row.document_name] = row

        guide_names = {guide.name for guide in GUIDES}
        for name, row in existing_by_name.items():
            if name not in guide_names:
                db.delete(row)
                stats["deleted"] = int(stats["deleted"]) + 1

        pending: list[tuple[DocumentGuide, str, PrepVector | None]] = []
        for guide in GUIDES:
            text = guide.to_text()
            row = existing_by_name.get(guide.name)
            if (
                row is not None
                and row.guide_text == text
                and row.embedding_openai is not None
                and row.embedding_ollama is not None
                and row.embedding_openai_model == cloud_spec.model
                and row.embedding_ollama_model == local_spec.model
            ):
                stats["skipped"] = int(stats["skipped"]) + 1
                continue
            pending.append((guide, text, row))

        if pending:
            cloud_embedder = get_embedding_model("prep", model_mode="cloud")
            local_embedder = get_embedding_model("prep", model_mode="local")
            texts = [text for _guide, text, _row in pending]
            cloud_vectors = cloud_embedder.embed_documents(texts)
            local_vectors = local_embedder.embed_documents(texts)

            for (guide, text, row), cloud_vector, local_vector in zip(
                pending,
                cloud_vectors,
                local_vectors,
            ):
                if row is None:
                    row = PrepVector(document_name=guide.name)
                    db.add(row)
                    stats["created"] = int(stats["created"]) + 1
                else:
                    stats["updated"] = int(stats["updated"]) + 1

                row.guide_text = text
                row.embedding_openai = cloud_vector
                row.embedding_ollama = local_vector
                row.embedding_openai_model = cloud_spec.model
                row.embedding_ollama_model = local_spec.model
                stats["written"] = int(stats["written"]) + 1

        db.commit()
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    result = build_prep_vectors_once()
    print(
        f"[prep-vectors] 가이드 {result['guides']}개 → "
        f"{result['written']}건 갱신, {result['skipped']}건 유지",
        flush=True,
    )
