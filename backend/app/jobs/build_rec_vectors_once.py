from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.model_provider import (
    get_embedding_model,
    resolve_embedding_model_spec_for_mode,
)
from app.models.normalized_policy import NormalizedPolicy
from app.models.recommend import RecommendationVector
from app.services.recommend import (
    VECTOR_TYPE_POLICY_RECOMMENDATION,
    build_recommendation_metadata,
    build_recommendation_text,
    fit_embedding_dim,
    source_hash,
)


def build_rec_vectors_once(force: bool = False, limit: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    stats = {
        "scanned": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }

    try:
        cloud_model, local_model = _embedding_models()
        cloud_spec = resolve_embedding_model_spec_for_mode("recommendation", "cloud")
        local_spec = resolve_embedding_model_spec_for_mode("recommendation", "local")
        query = (
            db.query(NormalizedPolicy)
            .filter(NormalizedPolicy.is_active.is_(True))
            .order_by(NormalizedPolicy.updated_at.desc())
        )
        if limit:
            query = query.limit(limit)

        for policy in query.all():
            stats["scanned"] += 1
            source_text = build_recommendation_text(policy)
            if not source_text.strip():
                stats["skipped"] += 1
                continue

            current_hash = source_hash(source_text)
            vector = (
                db.query(RecommendationVector)
                .filter(RecommendationVector.policy_id == policy.id)
                .filter(RecommendationVector.vector_type == VECTOR_TYPE_POLICY_RECOMMENDATION)
                .one_or_none()
            )

            if (
                vector
                and not force
                and vector.source_hash == current_hash
                and vector.embedding_status == "success"
                and vector.embedding_provider == "openai+ollama"
                and vector.embedding_openai_model == cloud_spec.model
                and vector.embedding_ollama_model == local_spec.model
                and vector.embedding_openai is not None
                and vector.embedding_ollama is not None
            ):
                stats["skipped"] += 1
                continue

            if vector is None:
                vector = RecommendationVector(
                    policy_id=policy.id,
                    vector_type=VECTOR_TYPE_POLICY_RECOMMENDATION,
                    source_text=source_text,
                    source_hash=current_hash,
                    embedding_provider="openai+ollama",
                    embedding_model=cloud_spec.model,
                    embedding_dim=cloud_spec.dimensions,
                    embedding_openai_model=cloud_spec.model,
                    embedding_ollama_model=local_spec.model,
                    embedding_status="pending",
                    vector_metadata=build_recommendation_metadata(policy),
                )
                db.add(vector)
                stats["created"] += 1
            else:
                vector.source_text = source_text
                vector.source_hash = current_hash
                vector.embedding_provider = "openai+ollama"
                vector.embedding_model = cloud_spec.model
                vector.embedding_dim = cloud_spec.dimensions
                vector.embedding_openai_model = cloud_spec.model
                vector.embedding_ollama_model = local_spec.model
                vector.embedding_status = "pending"
                vector.embedding_error = None
                vector.vector_metadata = build_recommendation_metadata(policy)
                stats["updated"] += 1

            try:
                cloud_embedding = fit_embedding_dim(
                    cloud_model.embed_text(source_text),
                    cloud_spec.dimensions,
                )
                local_embedding = fit_embedding_dim(
                    local_model.embed_text(source_text),
                    local_spec.dimensions,
                )
                vector.embedding_openai = cloud_embedding
                vector.embedding_ollama = local_embedding
                vector.embedding_status = "success"
                vector.embedding_error = None
                db.commit()
            except Exception as exc:
                db.rollback()
                vector = (
                    db.query(RecommendationVector)
                    .filter(RecommendationVector.policy_id == policy.id)
                    .filter(RecommendationVector.vector_type == VECTOR_TYPE_POLICY_RECOMMENDATION)
                    .one_or_none()
                )
                if vector is None:
                    vector = RecommendationVector(
                        policy_id=policy.id,
                        vector_type=VECTOR_TYPE_POLICY_RECOMMENDATION,
                        source_text=source_text,
                        source_hash=current_hash,
                        embedding_provider="openai+ollama",
                        embedding_model=cloud_spec.model,
                        embedding_dim=cloud_spec.dimensions,
                        embedding_openai_model=cloud_spec.model,
                        embedding_ollama_model=local_spec.model,
                        vector_metadata=build_recommendation_metadata(policy),
                    )
                    db.add(vector)
                vector.embedding_status = "failed"
                vector.embedding_error = type(exc).__name__
                db.commit()
                stats["failed"] += 1

        return stats
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def _embedding_models():
    return (
        get_embedding_model("recommendation", model_mode="cloud"),
        get_embedding_model("recommendation", model_mode="local"),
    )


if __name__ == "__main__":
    print(build_rec_vectors_once(), flush=True)
