from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.model_provider import (
    get_embedding_model,
    resolve_embedding_model_spec_for_mode,
)
from app.core.rag_utils import EmbeddingModel
from app.models.normalized_policy import NormalizedPolicy, PolicyDocument
from app.models.review import ReviewVector
from app.services.document_names import canonicalize


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

    멱등: 키·원문·모델·양쪽 벡터가 모두 같으면 건너뛴다.
    rebuild=True면 해당 정책의 기존 벡터를 지우고 다시 만든다.
    """
    # 정책 요건은 개인정보가 아니므로 두 모드의 검색 벡터를 미리 준비한다.
    # embedding_model 인자는 기존 테스트/관리 코드 호환을 위해 로컬 모델 override로 쓴다.
    cloud_embedder = get_embedding_model("document_review", model_mode="cloud")
    local_embedder = embedding_model or get_embedding_model(
        "document_review", model_mode="local"
    )
    cloud_spec = resolve_embedding_model_spec_for_mode("document_review", "cloud")
    local_spec = resolve_embedding_model_spec_for_mode("document_review", "local")

    db = SessionLocal()
    stats: dict[str, int | bool] = {
        "locked": False,
        "policies_scanned": 0,
        "vectors_created": 0,
        "vectors_updated": 0,
        "vectors_deleted": 0,
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
                _build_for_policy(
                    db,
                    policy,
                    cloud_embedder,
                    local_embedder,
                    cloud_spec.model,
                    local_spec.model,
                    rebuild,
                    stats,
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001 - 정책 하나가 전체를 막지 않게
                db.rollback()
                stats["errors"] = int(stats["errors"]) + 1
                print(
                    f"[review-vectors] policy={policy.id} failed error_type={type(exc).__name__}",
                    flush=True,
                )

        return stats
    finally:
        _release_advisory_lock(db)
        db.close()


def _build_for_policy(
    db: Session,
    policy: NormalizedPolicy,
    cloud_embedder: EmbeddingModel,
    local_embedder: EmbeddingModel,
    cloud_model_name: str,
    local_model_name: str,
    rebuild: bool,
    stats: dict[str, int | bool],
) -> None:
    if rebuild:
        db.query(ReviewVector).filter(ReviewVector.policy_id == policy.id).delete()
        db.flush()

    candidates = _collect_requirements(db, policy)
    existing = {
        (row.document_type, row.document_name): row
        for row in db.query(ReviewVector).filter(ReviewVector.policy_id == policy.id).all()
    }

    if not candidates:
        for row in existing.values():
            db.delete(row)
            stats["vectors_deleted"] = int(stats["vectors_deleted"]) + 1
        return

    candidate_keys = {
        (candidate["document_type"], candidate["document_name"])
        for candidate in candidates
    }
    for key, row in existing.items():
        if key not in candidate_keys:
            db.delete(row)
            stats["vectors_deleted"] = int(stats["vectors_deleted"]) + 1

    pending = []
    for candidate in candidates:
        row = existing.get((candidate["document_type"], candidate["document_name"]))
        if _review_vector_needs_refresh(
            row,
            candidate,
            cloud_model_name=cloud_model_name,
            local_model_name=local_model_name,
        ):
            pending.append((candidate, row))
    stats["skipped_existing"] = int(stats["skipped_existing"]) + (len(candidates) - len(pending))
    if not pending:
        return

    # bge-m3 컨텍스트(8192 토큰)를 넘지 않도록 원문을 잘라 임베딩한다
    texts = [c["source_text"][: settings.REVIEW_CHUNK_SIZE * 8] for c, _ in pending]

    cloud_vectors: list[list[float]] = []
    local_vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        cloud_vectors.extend(cloud_embedder.embed_documents(batch))
        local_vectors.extend(local_embedder.embed_documents(batch))

    for (candidate, row), cloud_vector, local_vector in zip(
        pending,
        cloud_vectors,
        local_vectors,
    ):
        if row is None:
            row = ReviewVector(
                policy_id=policy.id,
                document_name=candidate["document_name"],
                document_type=candidate["document_type"],
                source_text=candidate["source_text"],
            )
            db.add(row)
            stats["vectors_created"] = int(stats["vectors_created"]) + 1
        else:
            row.source_text = candidate["source_text"]
            stats["vectors_updated"] = int(stats["vectors_updated"]) + 1
        row.embedding_openai = cloud_vector
        row.embedding_ollama = local_vector
        row.embedding_openai_model = cloud_model_name
        row.embedding_ollama_model = local_model_name


def _review_vector_needs_refresh(
    row: ReviewVector | None,
    candidate: dict[str, str],
    *,
    cloud_model_name: str,
    local_model_name: str,
) -> bool:
    return bool(
        row is None
        or row.source_text != candidate["source_text"]
        or row.embedding_openai is None
        or row.embedding_ollama is None
        or row.embedding_openai_model != cloud_model_name
        or row.embedding_ollama_model != local_model_name
    )


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
    #
    # 공고 원문의 서류명은 그대로 쓸 수 없다. 표기가 제각각이고(사업자등록증 / 사본 /
    # 증명원 / 증명…), 한 항목에 여러 서류가 뭉쳐 있고(19%), 서류명이 아닌 것도
    # 섞여 있다("신청서", "구비서류"). 실측하면 고유 서류명이 411개인데, 정규화하면
    # 233개로 줄고 그중 31개가 전체의 55%를 커버한다.
    #
    # 정규화하지 않으면
    #   - 발급 가이드를 서류 하나당 일곱 번 써야 하고,
    #   - 요건 대조에서 '사업자등록증'과 '사업자등록증 사본'이 서로 다른 요건으로 잡혀
    #     한 파일이 하나만 커버하게 된다(1:1 배정이므로).
    for entry in policy.required_documents or []:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("name") or ""
        description = entry.get("description") or ""

        for name in canonicalize(raw_name):
            # 서류명 자체가 대조 기준이다. 설명이 있으면 붙여 문맥을 보강하되,
            # 원문 표기도 함께 넣어 검색에 잡히게 한다.
            source = " ".join(filter(None, [name, description, raw_name]))
            add("required_document", name, source)

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
