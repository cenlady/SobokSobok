from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.model_provider import get_embedding_model, normalize_model_mode
from app.core.rag_utils import search_generic_vectors
from app.models.prep import PrepVector


def prep_vector_column_for_mode(model_mode: str | None) -> tuple[str, Any]:
    selected_mode = normalize_model_mode(model_mode) or "local"
    column = (
        PrepVector.embedding_openai
        if selected_mode == "cloud"
        else PrepVector.embedding_ollama
    )
    return selected_mode, column


def search_prep_guides(
    db: Session,
    query: str,
    *,
    model_mode: str | None,
    limit: int = 5,
) -> list[tuple[PrepVector, float]]:
    normalized_query = query.strip()
    if not normalized_query or limit <= 0:
        return []

    selected_mode, vector_column = prep_vector_column_for_mode(model_mode)
    available = (
        db.query(func.count(PrepVector.id))
        .filter(vector_column.isnot(None))
        .scalar()
        or 0
    )
    if available == 0:
        return []

    embedder = get_embedding_model("prep", model_mode=selected_mode)
    return search_generic_vectors(
        db=db,
        model_class=PrepVector,
        query=normalized_query,
        embedding_model=embedder,
        embedding_column=vector_column,
        limit=limit,
    )
