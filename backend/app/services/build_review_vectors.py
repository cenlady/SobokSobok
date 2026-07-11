from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rag_utils import EmbeddingModel, OllamaEmbeddingModel
from app.models.normalized_policy import NormalizedPolicy, PolicyDocument
from app.models.review import ReviewVector


# policy_documents 중 요건 대조에 쓸 문서 유형
ELIGIBILITY_DOC_TYPES = ("requirements", "eligibility")

# 임베딩 요청당 청크 수 (bge-m3 배치)
EMBED_BATCH_SIZE = 32


def build_review_vectors_once(
    embedding_model: EmbeddingModel | None = None,
    rebuild: bool = False,
) -> dict[str, int | bool]:
    """[서류 검토 영역] 정책 요건 텍스트를 임베딩해 review_vectors를 채운다.

    소스 (공유 계약 #1: 텍스트만 읽고, 벡터는 이 서비스가 소유):
      - normalized_policies.required_documents[].name  → document_type="required_document"
      - policy_documents(requirements/eligibility).text → document_type=해당 유형

    멱등: (policy_id, document_type, document_name)이 이미 있으면 건너뛴다.
    rebuild=True면 해당 정책의 기존 벡터를 지우고 다시 만든다.
    """
    embedder = embedding_model or OllamaEmbeddingModel(
        model_name=settings.REVIEW_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )

    db = SessionLocal()
    stats: dict[str, int | bool] = {
        "locked": False,
        "policies_scanned": 0,
        "vectors_created": 0,
        "skipped_existing": 0,
        "errors": 0,
    }

    try:
        locked = _try_advisory_lock(db)
        stats["locked"] = locked
        if not locked:
            return stats

        policies = (
            db.query(NormalizedPolicy)
            .filter(NormalizedPolicy.is_active.is_(True))
            .order_by(NormalizedPolicy.created_at)
            .all()
        )

        for policy in policies:
            stats["policies_scanned"] = int(stats["policies_scanned"]) + 1
            try:
                _build_for_policy(db, policy, embedder, rebuild, stats)
                db.commit()
            except Exception as exc:  # noqa: BLE001 - 정책 하나가 전체를 막지 않게
                db.rollback()
                stats["errors"] = int(stats["errors"]) + 1
                print(f"[review-vectors] policy={policy.id} failed: {exc}", flush=True)

        return stats
    finally:
        _release_advisory_lock(db)
        db.close()


def _build_for_policy(
    db: Session,
    policy: NormalizedPolicy,
    embedder: EmbeddingModel,
    rebuild: bool,
    stats: dict[str, int | bool],
) -> None:
    if rebuild:
        db.query(ReviewVector).filter(ReviewVector.policy_id == policy.id).delete()
        db.flush()

    candidates = _collect_requirements(db, policy)
    if not candidates:
        return

    existing = set()
    if not rebuild:
        existing = {
            (row.document_type, row.document_name)
            for row in db.query(ReviewVector).filter(ReviewVector.policy_id == policy.id).all()
        }

    pending = [c for c in candidates if (c["document_type"], c["document_name"]) not in existing]
    stats["skipped_existing"] = int(stats["skipped_existing"]) + (len(candidates) - len(pending))
    if not pending:
        return

    # bge-m3 컨텍스트(8192 토큰)를 넘지 않도록 원문을 잘라 임베딩한다
    texts = [c["source_text"][: settings.REVIEW_CHUNK_SIZE * 8] for c in pending]

    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        vectors.extend(embedder.embed_documents(texts[start : start + EMBED_BATCH_SIZE]))

    for candidate, vector in zip(pending, vectors):
        db.add(
            ReviewVector(
                policy_id=policy.id,
                document_name=candidate["document_name"],
                document_type=candidate["document_type"],
                source_text=candidate["source_text"],
                embedding=vector,
            )
        )
        stats["vectors_created"] = int(stats["vectors_created"]) + 1


def _collect_requirements(db: Session, policy: NormalizedPolicy) -> list[dict[str, str]]:
    """정책에서 요건 대조 대상 텍스트를 모은다. (document_type, document_name, source_text)"""
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(document_type: str, document_name: str, source_text: str | None) -> None:
        name = (document_name or "").strip()
        body = (source_text or "").strip()
        if not name or not body:
            return
        key = (document_type, name[:255])
        if key in seen:
            return
        seen.add(key)
        items.append(
            {
                "document_type": document_type,
                "document_name": name[:255],
                "source_text": body,
            }
        )

    # 1) 필수 제출 서류 — [{name, description, ...}]
    for entry in policy.required_documents or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        description = entry.get("description") or ""
        # 서류명 자체가 대조 기준이므로 설명이 있으면 붙여 문맥을 보강한다
        add("required_document", name, f"{name} {description}".strip())

    # 2) 지원대상 요건 텍스트 (자연어)
    add("eligibility", "지원 대상", policy.target_text)

    # 3) 정규화된 요건/대상 문서 (policy_documents)
    documents = (
        db.query(PolicyDocument)
        .filter(
            PolicyDocument.policy_id == policy.id,
            PolicyDocument.document_type.in_(ELIGIBILITY_DOC_TYPES),
        )
        .all()
    )
    for document in documents:
        add(document.document_type, document.title or document.document_type, document.text)

    return items


def _try_advisory_lock(db: Session) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": settings.REVIEW_VECTORS_ADVISORY_LOCK_ID},
        ).scalar()
    )


def _release_advisory_lock(db: Session) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": settings.REVIEW_VECTORS_ADVISORY_LOCK_ID},
    )
    db.commit()
