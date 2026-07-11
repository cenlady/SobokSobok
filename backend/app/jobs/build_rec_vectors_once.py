from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rag_utils import OllamaEmbeddingModel, OpenAIEmbeddingModel
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
        model = _embedding_model()
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
                and vector.embedding_model == _model_name()
                and vector.embedding_dim == settings.REC_EMBEDDING_DIM
            ):
                stats["skipped"] += 1
                continue

            if vector is None:
                vector = RecommendationVector(
                    policy_id=policy.id,
                    vector_type=VECTOR_TYPE_POLICY_RECOMMENDATION,
                    source_text=source_text,
                    source_hash=current_hash,
                    embedding_provider=settings.REC_EMBEDDING_PROVIDER,
                    embedding_model=_model_name(),
                    embedding_dim=settings.REC_EMBEDDING_DIM,
                    embedding_status="pending",
                    vector_metadata=build_recommendation_metadata(policy),
                )
                db.add(vector)
                stats["created"] += 1
            else:
                vector.source_text = source_text
                vector.source_hash = current_hash
                vector.embedding_provider = settings.REC_EMBEDDING_PROVIDER
                vector.embedding_model = _model_name()
                vector.embedding_dim = settings.REC_EMBEDDING_DIM
                vector.embedding_status = "pending"
                vector.embedding_error = None
                vector.vector_metadata = build_recommendation_metadata(policy)
                stats["updated"] += 1

            try:
                embedding = model.embed_text(source_text)
                vector.embedding = fit_embedding_dim(embedding, settings.REC_EMBEDDING_DIM)
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
                        embedding_provider=settings.REC_EMBEDDING_PROVIDER,
                        embedding_model=_model_name(),
                        embedding_dim=settings.REC_EMBEDDING_DIM,
                        vector_metadata=build_recommendation_metadata(policy),
                    )
                    db.add(vector)
                vector.embedding_status = "failed"
                vector.embedding_error = str(exc)[:1000]
                db.commit()
                stats["failed"] += 1

        return stats
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def _embedding_model():
    if settings.REC_EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingModel(model_name=settings.REC_OPENAI_MODEL)
    return OllamaEmbeddingModel(
        model_name=settings.REC_OLLAMA_MODEL,
        base_url=settings.REC_OLLAMA_BASE_URL,
    )


def _model_name() -> str:
    if settings.REC_EMBEDDING_PROVIDER == "openai":
        return settings.REC_OPENAI_MODEL
    return settings.REC_OLLAMA_MODEL


if __name__ == "__main__":
    print(build_rec_vectors_once(), flush=True)
