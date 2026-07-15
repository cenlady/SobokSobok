import uuid
import hashlib
import re
from collections.abc import Iterator
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_errors import ModelResponseError
from app.core.model_provider import (
    get_chat_model,
    get_embedding_model,
    normalize_model_mode,
    resolve_embedding_model_spec_for_mode,
)
from app.core.rag_utils import (
    EmbeddingModel,
    SimpleTextSplitter,
    search_policy_chunks,
)
from app.models.chat import ChatMessage, ChatSession, PolicyChunk
from app.models.normalized_policy import NormalizedPolicy, PolicyDocument


DOCUMENT_TYPE_INTENTS: Dict[str, List[str]] = {
    "summary": ["summary", "support_content"],
    "support_content": ["support_content", "benefit"],
    "eligibility": ["eligibility", "target"],
    "application": ["application", "apply_method"],
    "deadline": ["deadline", "schedule"],
    "requirements": ["requirements", "documents"],
    "contact": ["contact"],
    "procedure": ["procedure", "application"],
    "reference": ["reference"],
    "body": ["general"],
    "section": ["general"],
}

DOCUMENT_TYPE_SECTION_LABELS: Dict[str, str] = {
    "summary": "정책 요약",
    "support_content": "지원 내용",
    "eligibility": "지원 대상",
    "application": "신청 방법",
    "deadline": "신청 기한",
    "requirements": "구비 서류",
    "contact": "문의처",
    "procedure": "신청 절차",
    "reference": "참고 사항",
    "body": "공고 본문",
    "section": "공고 본문",
}

KEYWORD_INTENTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("eligibility", ("지원대상", "지원 대상", "신청대상", "신청 대상", "대상자", "자격", "요건", "누가", "누구", "받을 수", "가능", "소상공인", "중소기업")),
    ("requirements", ("제출서류", "구비서류", "필요서류", "첨부서류", "서류", "증빙")),
    ("application", ("신청", "접수", "온라인", "방문", "우편", "이메일", "제출")),
    ("deadline", ("마감", "기간", "접수기간", "신청기간", "시작일", "종료일")),
    ("contact", ("문의", "연락처", "전화", "담당자", "접수처", "기관")),
    ("benefit", ("지원내용", "지원금", "혜택", "금액", "보조금", "융자", "교육", "컨설팅")),
    ("region", ("지역", "시도", "시군구", "전국", "서울", "경기", "부산")),
    ("procedure", ("절차", "선정", "평가", "심사", "발표", "선발")),
]

SMALL_BUSINESS_DOMAIN_KEYWORDS: Tuple[str, ...] = (
    "소상공인",
    "소기업",
    "소공인",
    "자영업",
    "사업자",
    "사업장",
    "중소기업",
    "전통시장",
    "상점가",
    "창업",
    "폐업",
    "재기",
    "매출",
    "점포",
    "상권",
    "경영",
    "기업",
    "노란우산",
)

NON_BUSINESS_POLICY_HINTS: Tuple[str, ...] = (
    "자원봉사",
    "봉사자",
    "복지시설",
)

QUESTION_HINTS: Dict[str, List[str]] = {
    "summary": ["이 공고가 뭐야?", "핵심 내용만 요약해줘."],
    "support_content": ["무엇을 지원해줘?", "지원 내용이 뭐야?"],
    "benefit": ["얼마나 지원받을 수 있어?", "어떤 혜택이 있어?"],
    "eligibility": ["누가 신청할 수 있어?", "지원 대상 조건이 뭐야?"],
    "target": ["내 사업자가 대상인지 알려줘.", "대상 업종이 정해져 있어?"],
    "requirements": ["필요한 서류가 뭐야?", "제출해야 하는 증빙이 있어?"],
    "documents": ["신청 서류 목록 알려줘.", "구비서류를 정리해줘."],
    "application": ["어디서 신청해?", "신청 방법을 알려줘."],
    "apply_method": ["온라인 신청 가능해?", "방문 접수해야 해?"],
    "deadline": ["언제까지 신청해야 해?", "접수 기간이 언제야?"],
    "schedule": ["마감일이 언제야?", "신청 시작일과 종료일 알려줘."],
    "contact": ["문의처가 어디야?", "담당 기관 연락처 알려줘."],
    "procedure": ["선정 절차가 어떻게 돼?", "심사는 어떻게 진행돼?"],
    "region": ["어느 지역 공고야?", "우리 지역에서도 신청 가능해?"],
    "reference": ["원문 기준이 어디야?", "참고할 자료가 있어?"],
    "general": ["이 정책에 대해 알려줘.", "내 상황에 맞는지 설명해줘."],
}


def _compact_list(values: Any, limit: int = 6) -> List[str]:
    if not isinstance(values, list):
        return []
    compacted = [str(value) for value in values if value not in (None, "")]
    return compacted[:limit]


def _format_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def infer_intent_tags(document_type: Optional[str], title: Optional[str], text: str) -> List[str]:
    tags: List[str] = []
    if document_type:
        tags.extend(DOCUMENT_TYPE_INTENTS.get(document_type, [document_type]))

    searchable = f"{document_type or ''}\n{title or ''}\n{text or ''}"
    for intent, keywords in KEYWORD_INTENTS:
        if any(keyword in searchable for keyword in keywords):
            tags.append(intent)

    return _dedupe_preserve_order(tags or ["general"])


def build_question_hints(intent_tags: List[str]) -> List[str]:
    hints: List[str] = []
    for tag in intent_tags:
        hints.extend(QUESTION_HINTS.get(tag, []))
    return _dedupe_preserve_order(hints)[:10]


def build_policy_document_metadata(
    policy: NormalizedPolicy,
    document: PolicyDocument,
    intent_tags: List[str],
) -> Dict[str, Any]:
    return {
        "policy_id": str(policy.id),
        "document_id": str(document.id),
        "document_type": document.document_type,
        "document_title": document.title,
        "section_title": document.title or DOCUMENT_TYPE_SECTION_LABELS.get(
            document.document_type,
            document.document_type,
        ),
        "source_ref": document.source_ref,
        "policy_title": policy.title,
        "policy_summary": policy.summary,
        "organization": policy.organization,
        "support_type": policy.support_type,
        "status": policy.status,
        "apply_start": _format_datetime(policy.apply_start),
        "apply_end": _format_datetime(policy.apply_end),
        "apply_url": policy.apply_url,
        "region_scope": policy.region_scope,
        "sido": policy.sido,
        "sigungu": policy.sigungu,
        "matched_sidos": _compact_list(policy.matched_sidos),
        "application_methods": _compact_list(policy.application_methods),
        "contact_points": _compact_list(policy.contact_points),
        "required_document_count": policy.required_document_count,
        "has_required_documents": policy.has_required_documents,
        "industry_tags": _compact_list(policy.industry_tags),
        "business_status_tags": _compact_list(policy.business_status_tags),
        "intent_tags": intent_tags,
        "question_hints": build_question_hints(intent_tags),
    }


def build_embedding_context(metadata: Dict[str, Any]) -> str:
    question_hints = ", ".join(metadata.get("question_hints") or [])
    intent_tags = ", ".join(metadata.get("intent_tags") or [])
    period = " ~ ".join(
        value for value in [metadata.get("apply_start"), metadata.get("apply_end")] if value
    )
    contact_points = ", ".join(metadata.get("contact_points") or [])
    application_methods = ", ".join(metadata.get("application_methods") or [])

    parts = [
        f"정책명: {metadata.get('policy_title')}",
        f"문서유형: {metadata.get('document_type')}",
        f"문서제목: {metadata.get('document_title')}",
        f"섹션: {metadata.get('section_title')}",
        f"기관: {metadata.get('organization')}",
        f"지역: {metadata.get('region_scope')} {metadata.get('sido') or ''} {metadata.get('sigungu') or ''}".strip(),
        f"상태: {metadata.get('status')}",
        f"신청기간: {period}" if period else "",
        f"신청방법: {application_methods}" if application_methods else "",
        f"문의처: {contact_points}" if contact_points else "",
        f"질문 의도 태그: {intent_tags}" if intent_tags else "",
        f"예상 질문: {question_hints}" if question_hints else "",
    ]
    return "\n".join(part for part in parts if part and "None" not in part)


def build_chunk_embedding_input(embedding_context: str, chunk_text: str) -> str:
    """문서 메타데이터와 청크 본문을 구분해 임베딩 입력을 만듭니다."""
    return f"{embedding_context}\n청크 본문:\n{chunk_text}".strip()


def build_query_embedding_text(query: str, *, policy_id: Optional[uuid.UUID] = None) -> str:
    intent_tags = infer_intent_tags(None, None, query)
    hints = build_question_hints(intent_tags)
    domain_context = ""
    if policy_id is None:
        domain_context = (
            "\n검색 도메인: 소상공인, 소기업, 자영업자, 사업자, 중소기업 대상 정책 공고"
        )
    if not hints:
        return f"{query}{domain_context}"
    return (
        f"사용자 질문: {query}\n"
        f"질문 의도: {', '.join(intent_tags)}\n"
        f"관련 표현: {', '.join(hints)}"
        f"{domain_context}"
    )


def ensure_policy_chunk_embedding_dimension(db: Session) -> Dict[str, Any]:
    """
    policy_chunks의 OpenAI/Ollama 컬럼을 각각의 설정 차원에 맞춥니다.
    기존 차원이 다르면 두 임베딩을 함께 재생성해야 하므로 청크를 비웁니다.
    """
    if not settings.database_url.startswith("postgresql"):
        return {"checked": False, "reason": "non-postgresql database"}

    expected_dims = {
        "embedding_openai": int(settings.CHAT_CLOUD_EMBEDDING_DIMENSIONS),
        "embedding_ollama": int(settings.CHAT_LOCAL_EMBEDDING_DIMENSIONS),
    }
    if any(dimension <= 0 for dimension in expected_dims.values()):
        raise ValueError("CHAT_*_EMBEDDING_DIMENSIONS는 양수여야 합니다.")

    current_types: Dict[str, str | None] = {}
    for column_name in expected_dims:
        current_types[column_name] = db.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE c.relname = 'policy_chunks'
                  AND n.nspname = 'public'
                  AND a.attname = :column_name
                  AND NOT a.attisdropped
                """
            ),
            {"column_name": column_name},
        ).scalar()

    expected_types = {
        column_name: f"vector({dimension})"
        for column_name, dimension in expected_dims.items()
    }
    if current_types == expected_types:
        return {"checked": True, "changed": False, "current_types": current_types}

    before_count = db.query(func.count(PolicyChunk.id)).scalar() or 0
    if any(
        current_types[column_name] not in (None, expected_types[column_name])
        for column_name in expected_dims
    ):
        db.execute(text("DELETE FROM policy_chunks"))

    for column_name, dimension in expected_dims.items():
        current_type = current_types[column_name]
        if current_type is None:
            db.execute(
                text(
                    f"ALTER TABLE policy_chunks ADD COLUMN {column_name} vector({dimension})"
                )
            )
        elif current_type != expected_types[column_name]:
            db.execute(
                text(
                    f"ALTER TABLE policy_chunks "
                    f"ALTER COLUMN {column_name} TYPE vector({dimension})"
                )
            )
    db.commit()

    return {
        "checked": True,
        "changed": True,
        "previous_types": current_types,
        "current_types": expected_types,
        "deleted_chunks": before_count if before_count else 0,
    }


def build_policy_chunks(
    db: Session,
    *,
    policy_id: Optional[uuid.UUID] = None,
    limit: Optional[int] = None,
    force: bool = False,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> Dict[str, Any]:
    cloud_spec = resolve_embedding_model_spec_for_mode("chat", "cloud")
    local_spec = resolve_embedding_model_spec_for_mode("chat", "local")
    schema_result = ensure_policy_chunk_embedding_dimension(db)
    model_name_log = f"openai:{cloud_spec.model}+ollama:{local_spec.model}"

    query = (
        db.query(PolicyDocument)
        .join(PolicyDocument.policy)
        .filter(PolicyDocument.text.isnot(None))
        .order_by(PolicyDocument.created_at.asc(), PolicyDocument.id.asc())
    )
    if policy_id:
        query = query.filter(PolicyDocument.policy_id == policy_id)
    if force and limit:
        query = query.limit(limit)

    documents = query.all()
    existing_chunks_by_document: Dict[uuid.UUID, List[PolicyChunk]] = {}
    if not force and documents:
        document_ids = [document.id for document in documents]
        existing_chunks = (
            db.query(PolicyChunk)
            .filter(PolicyChunk.document_id.in_(document_ids))
            .order_by(PolicyChunk.document_id, PolicyChunk.chunk_index)
            .all()
        )
        for chunk in existing_chunks:
            existing_chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

    actual_chunk_size = chunk_size or settings.CHAT_CHUNK_SIZE
    actual_chunk_overlap = chunk_overlap or settings.CHAT_CHUNK_OVERLAP
    stats: Dict[str, Any] = {
        "embedding_models": {
            "cloud": f"openai:{cloud_spec.model}:{cloud_spec.dimensions}",
            "local": f"ollama:{local_spec.model}:{local_spec.dimensions}",
        },
        "chunk_size": actual_chunk_size,
        "chunk_overlap": actual_chunk_overlap,
        "force": force,
        "schema": schema_result,
        "target_documents": len(documents),
        "embedded_documents": 0,
        "skipped_documents": 0,
        "metadata_backfilled": 0,
        "failed_documents": 0,
        "created_chunks": 0,
        "failures": [],
    }

    splitter = SimpleTextSplitter(chunk_size=actual_chunk_size, chunk_overlap=actual_chunk_overlap)
    prepared_chunks: List[Dict[str, Any]] = []
    documents_to_replace: set[uuid.UUID] = set()

    for document in documents:
        try:
            policy = document.policy
            intent_tags = infer_intent_tags(document.document_type, document.title, document.text)
            metadata = build_policy_document_metadata(policy, document, intent_tags)
            embedding_context = build_embedding_context(metadata)
            seen_hashes = set()
            document_chunks = []
            for raw_chunk in splitter.split_text(document.text):
                chunk_hash = hashlib.sha256(raw_chunk.encode("utf-8")).hexdigest()
                if chunk_hash in seen_hashes:
                    continue
                seen_hashes.add(chunk_hash)
                document_chunks.append((raw_chunk, chunk_hash))

            prepared_document_chunks: List[Dict[str, Any]] = []
            for chunk_index, (chunk_text, chunk_hash) in enumerate(document_chunks):
                embedding_input = build_chunk_embedding_input(embedding_context, chunk_text)
                embedding_source_hash = hashlib.sha256(
                    embedding_input.encode("utf-8")
                ).hexdigest()
                prepared_document_chunks.append(
                    {
                        "policy_id": document.policy_id,
                        "document_id": document.id,
                        "chunk_index": chunk_index,
                        "chunk_text": chunk_text,
                        "chunk_hash": chunk_hash,
                        "metadata": {
                            **metadata,
                            "chunk_size": actual_chunk_size,
                            "chunk_overlap": actual_chunk_overlap,
                            "length": len(chunk_text),
                            "embedding_input_strategy": "document_context_section_plus_chunk",
                            "embedding_source_hash": embedding_source_hash,
                        },
                        "embedding_input": embedding_input,
                        "embedding_source_hash": embedding_source_hash,
                    }
                )

            existing_document_chunks = existing_chunks_by_document.get(document.id, [])
            if not force and _policy_chunks_are_current(
                existing_document_chunks,
                prepared_document_chunks,
                cloud_model_name=cloud_spec.model,
                local_model_name=local_spec.model,
            ):
                for existing, prepared in zip(
                    sorted(existing_document_chunks, key=lambda chunk: chunk.chunk_index),
                    prepared_document_chunks,
                ):
                    metadata = (
                        existing.chunk_metadata
                        if isinstance(existing.chunk_metadata, dict)
                        else {}
                    )
                    if not metadata.get("embedding_source_hash"):
                        existing.chunk_metadata = prepared["metadata"]
                        stats["metadata_backfilled"] += 1
                stats["skipped_documents"] += 1
                continue

            if not force and limit and len(documents_to_replace) >= limit:
                break

            documents_to_replace.add(document.id)
            prepared_chunks.extend(prepared_document_chunks)
            if prepared_document_chunks:
                stats["embedded_documents"] += 1
                stats["created_chunks"] += len(prepared_document_chunks)
        except Exception as exc:
            db.rollback()
            stats["failed_documents"] += 1
            stats["failures"].append(
                {
                    "document_id": str(document.id),
                    "policy_id": str(document.policy_id),
                    "error_type": type(exc).__name__,
                }
            )

    if not documents_to_replace:
        if stats["metadata_backfilled"]:
            db.commit()
        return stats

    try:
        (
            db.query(PolicyChunk)
            .filter(PolicyChunk.document_id.in_(documents_to_replace))
            .delete(synchronize_session=False)
        )
        db.flush()

        if prepared_chunks:
            cloud_embedding_model = get_embedding_model("chat", model_mode="cloud")
            local_embedding_model = get_embedding_model("chat", model_mode="local")
            batch_size = 100
            for start in range(0, len(prepared_chunks), batch_size):
                batch = prepared_chunks[start:start + batch_size]
                inputs = [item["embedding_input"] for item in batch]
                cloud_embeddings = cloud_embedding_model.embed_documents(inputs)
                local_embeddings = local_embedding_model.embed_documents(inputs)
                for item, cloud_vector, local_vector in zip(
                    batch,
                    cloud_embeddings,
                    local_embeddings,
                ):
                    db.add(
                        PolicyChunk(
                            policy_id=item["policy_id"],
                            document_id=item["document_id"],
                            chunk_index=item["chunk_index"],
                            chunk_text=item["chunk_text"],
                            chunk_hash=item["chunk_hash"],
                            chunk_metadata=item["metadata"],
                            embedding_status="success",
                            embedding_model=model_name_log,
                            embedding_openai=cloud_vector,
                            embedding_ollama=local_vector,
                            embedding_openai_model=cloud_spec.model,
                            embedding_ollama_model=local_spec.model,
                            created_at=func.now(),
                        )
                    )
            db.flush()
        db.commit()
    except Exception as exc:
        db.rollback()
        stats["failed_documents"] = len(documents_to_replace)
        stats["embedded_documents"] = 0
        stats["created_chunks"] = 0
        stats["failures"].append({"error_type": type(exc).__name__})

    return stats


def _policy_chunks_are_current(
    existing_chunks: List[PolicyChunk],
    prepared_chunks: List[Dict[str, Any]],
    *,
    cloud_model_name: str,
    local_model_name: str,
) -> bool:
    """본문·검색 문맥·모델·양쪽 벡터가 모두 같을 때만 재임베딩을 건너뛴다."""
    if len(existing_chunks) != len(prepared_chunks):
        return False

    ordered_existing = sorted(existing_chunks, key=lambda chunk: chunk.chunk_index)
    for existing, prepared in zip(ordered_existing, prepared_chunks):
        metadata = (
            existing.chunk_metadata if isinstance(existing.chunk_metadata, dict) else {}
        )
        stored_source_hash = metadata.get("embedding_source_hash")
        if stored_source_hash:
            source_matches = stored_source_hash == prepared["embedding_source_hash"]
        else:
            prepared_metadata = prepared.get("metadata") or {}
            source_matches = (
                existing.chunk_text == prepared.get("chunk_text")
                and metadata
                == {
                    key: value
                    for key, value in prepared_metadata.items()
                    if key != "embedding_source_hash"
                }
            )

        if (
            existing.chunk_index != prepared["chunk_index"]
            or existing.chunk_hash != prepared["chunk_hash"]
            or not source_matches
            or existing.embedding_status != "success"
            or existing.embedding_openai is None
            or existing.embedding_ollama is None
            or existing.embedding_openai_model != cloud_model_name
            or existing.embedding_ollama_model != local_model_name
        ):
            return False
    return True


def get_policy_chunk_stats(db: Session) -> Dict[str, Any]:
    return {
        "policy_documents": db.query(func.count(PolicyDocument.id)).scalar() or 0,
        "policy_chunks": db.query(func.count(PolicyChunk.id)).scalar() or 0,
        "embedded_chunks": (
            db.query(func.count(PolicyChunk.id))
            .filter(PolicyChunk.embedding_status == "success")
            .scalar()
            or 0
        ),
        "cloud_embedded_chunks": (
            db.query(func.count(PolicyChunk.id))
            .filter(PolicyChunk.embedding_openai.isnot(None))
            .scalar()
            or 0
        ),
        "local_embedded_chunks": (
            db.query(func.count(PolicyChunk.id))
            .filter(PolicyChunk.embedding_ollama.isnot(None))
            .scalar()
            or 0
        ),
        "failed_chunks": (
            db.query(func.count(PolicyChunk.id))
            .filter(PolicyChunk.embedding_status == "failed")
            .scalar()
            or 0
        ),
        "chunked_documents": db.query(func.count(func.distinct(PolicyChunk.document_id))).scalar() or 0,
    }


def chunk_to_source(chunk: PolicyChunk, similarity: float) -> Dict[str, Any]:
    metadata = dict(chunk.chunk_metadata or {})
    policy = chunk.policy
    if policy is not None:
        metadata.setdefault("policy_title", policy.title)
        metadata.setdefault("policy_summary", policy.summary)
        metadata.setdefault("organization", policy.organization)
        metadata.setdefault("support_type", policy.support_type)
        metadata.setdefault("industry_tags", _compact_list(policy.industry_tags))
        metadata.setdefault("business_status_tags", _compact_list(policy.business_status_tags))
    display_text = clean_rag_evidence_text(chunk.chunk_text)
    answer_text = clean_rag_answer_text(chunk.chunk_text)
    return {
        "chunk_id": str(chunk.id),
        "policy_id": str(chunk.policy_id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "similarity": similarity,
        "chunk_text": display_text,
        "answer_text": answer_text,
        "raw_chunk_text": chunk.chunk_text,
        "metadata": metadata,
        "policy_title": metadata.get("policy_title"),
        "document_type": metadata.get("document_type"),
        "document_title": metadata.get("document_title"),
        "source_ref": metadata.get("source_ref"),
        "apply_start": metadata.get("apply_start"),
        "apply_end": metadata.get("apply_end"),
        "contact_points": metadata.get("contact_points") or [],
        "question_hints": metadata.get("question_hints") or [],
    }


def policy_document_to_source(
    policy: NormalizedPolicy,
    document: PolicyDocument,
) -> Dict[str, Any]:
    """상세 채팅에서 부모 문서 전체를 기존 근거 응답 형식으로 변환한다."""
    intent_tags = infer_intent_tags(
        document.document_type,
        document.title,
        document.text,
    )
    metadata = build_policy_document_metadata(policy, document, intent_tags)
    metadata["retrieval_mode"] = "parent_document"
    display_text = clean_rag_evidence_text(document.text)
    answer_text = clean_rag_answer_text(document.text)
    return {
        # 프론트/응답 스키마 호환을 위해 부모 문서 ID를 근거 ID로 사용한다.
        "chunk_id": str(document.id),
        "policy_id": str(policy.id),
        "document_id": str(document.id),
        "chunk_index": 0,
        "similarity": 1.0,
        "rerank_score": 1.0,
        "chunk_text": display_text,
        "answer_text": answer_text,
        "raw_chunk_text": document.text,
        "metadata": metadata,
        "policy_title": policy.title,
        "document_type": document.document_type,
        "document_title": document.title,
        "source_ref": document.source_ref,
        "apply_start": metadata.get("apply_start"),
        "apply_end": metadata.get("apply_end"),
        "contact_points": metadata.get("contact_points") or [],
        "question_hints": metadata.get("question_hints") or [],
    }


def rerank_sources_by_intent(
    sources: List[Dict[str, Any]],
    query_intent_tags: List[str],
    *,
    prefer_small_business_domain: bool = False,
) -> List[Dict[str, Any]]:
    query_intents = set(query_intent_tags)
    reranked = []

    for source in sources:
        metadata = source.get("metadata") or {}
        source_intents = set(metadata.get("intent_tags") or [])
        document_type = source.get("document_type")
        intent_matches = query_intents & source_intents

        bonus = 0.0
        if intent_matches:
            bonus += 0.06 + min(len(intent_matches), 3) * 0.01
        if document_type in query_intents:
            bonus += 0.04
        if "eligibility" in query_intents and document_type == "eligibility":
            bonus += 0.07
        if "requirements" in query_intents and document_type == "requirements":
            bonus += 0.07
        if "contact" in query_intents and document_type == "contact":
            bonus += 0.07
        if "deadline" in query_intents and document_type == "deadline":
            bonus += 0.07
        if document_type == "body" and not intent_matches:
            bonus -= 0.02
        if prefer_small_business_domain:
            bonus += small_business_domain_bonus(source)

        source["rerank_score"] = source["similarity"] + bonus
        reranked.append(source)

    return sorted(reranked, key=lambda item: item["rerank_score"], reverse=True)


def small_business_domain_bonus(source: Dict[str, Any]) -> float:
    metadata = source.get("metadata") or {}
    parts = [
        source.get("policy_title"),
        source.get("document_title"),
        source.get("chunk_text"),
        metadata.get("policy_summary"),
        metadata.get("organization"),
        metadata.get("support_type"),
        " ".join(metadata.get("industry_tags") or []),
        " ".join(metadata.get("business_status_tags") or []),
    ]
    searchable = " ".join(str(part) for part in parts if part).lower()
    has_business_signal = any(keyword in searchable for keyword in SMALL_BUSINESS_DOMAIN_KEYWORDS)
    has_non_business_signal = any(keyword in searchable for keyword in NON_BUSINESS_POLICY_HINTS)

    if has_business_signal:
        return 0.18
    if has_non_business_signal:
        return -0.18
    return -0.08


GLOBAL_POLICY_SCORE_MARGIN = 0.08
GENERIC_POLICY_ATTRIBUTE_KEYWORDS: Tuple[str, ...] = (
    "지원 대상",
    "대상이 누구",
    "누가 신청",
    "신청 자격",
    "지원 내용",
    "얼마 지원",
    "신청 서류",
    "구비 서류",
    "필요 서류",
    "신청 방법",
    "어떻게 신청",
    "접수처",
    "신청 기간",
    "마감",
    "문의처",
)


def build_policy_candidates(
    sources: List[Dict[str, Any]],
    *,
    max_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """검색 청크를 공고 단위 후보로 묶는다.

    메인 채팅은 서로 다른 공고의 문장을 한 답변에 섞으면 안 되므로,
    같은 공고의 최고 점수와 근거 개수를 이용해 사용자가 고를 후보를 만든다.
    """
    candidates_by_policy: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        policy_id = str(source.get("policy_id") or "")
        if not policy_id:
            continue

        score = float(source.get("rerank_score", source.get("similarity", 0.0)) or 0.0)
        existing = candidates_by_policy.get(policy_id)
        if existing is None:
            metadata = source.get("metadata") or {}
            candidates_by_policy[policy_id] = {
                "policy_id": policy_id,
                "title": source.get("policy_title") or "정책 공고",
                "summary": metadata.get("policy_summary"),
                "support_type": metadata.get("support_type"),
                "apply_end": source.get("apply_end") or metadata.get("apply_end"),
                "score": score,
                "source_count": 1,
            }
            continue

        existing["source_count"] += 1
        if score > existing["score"]:
            existing["score"] = score

    return sorted(
        candidates_by_policy.values(),
        key=lambda candidate: candidate["score"],
        reverse=True,
    )[:max_candidates]


def should_request_policy_selection(
    query: str,
    intent_tags: List[str],
    candidates: List[Dict[str, Any]],
    *,
    policy_id: Optional[uuid.UUID],
) -> bool:
    """공고가 특정되지 않은 메인 채팅에서만 후보 선택을 요청한다."""
    if policy_id is not None or len(candidates) < 2:
        return False

    normalized_query = _normalize_space(query).lower()
    normalized_titles = [
        _normalize_space(str(candidate.get("title") or "")).lower()
        for candidate in candidates
    ]
    if any(title and title in normalized_query for title in normalized_titles):
        return False

    # "지원 대상이 누구야?", "서류가 뭐야?"처럼 공고명을 전혀 주지 않은 질문은
    # 유사도가 높더라도 임의의 한 공고를 골라 답하지 않는다.
    has_generic_attribute_question = any(
        keyword in normalized_query for keyword in GENERIC_POLICY_ATTRIBUTE_KEYWORDS
    ) or any(
        tag in intent_tags
        for tag in ("eligibility", "target", "requirements", "documents", "deadline", "contact")
    )
    if has_generic_attribute_question and len(normalized_query) <= 20:
        return True

    return (candidates[0]["score"] - candidates[1]["score"]) < GLOBAL_POLICY_SCORE_MARGIN


def build_policy_selection_answer(candidates: List[Dict[str, Any]]) -> str:
    if not candidates:
        return "질문과 가장 가까운 공고를 고르지 못했어요. 공고명이나 지원 분야를 조금 더 알려주세요."

    return (
        "여러 정책 공고가 비슷하게 검색됐어요.\n\n"
        "아래에서 궁금한 공고를 하나 고르면, 그 공고문만 기준으로 지원 대상·서류·신청 기간을 정확히 안내할게요."
    )


FOLLOW_UP_CONTEXT_KEYWORDS: Tuple[str, ...] = (
    "그거",
    "그 공고",
    "그 정책",
    "이 공고",
    "이 정책",
    "해당 공고",
    "그럼",
    "아까",
    "방금",
    "위에",
    "요약해",
)
RECOMMENDATION_FOLLOW_UP_KEYWORDS: Tuple[str, ...] = (
    "추천",
    "왜",
    "이유",
    "근거",
    "아까",
    "방금",
    "위에",
    "그 정책",
    "그 공고",
    "이 정책",
    "이 공고",
    "지역",
    "서울",
    "경기",
    "경기도",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "강원",
    "충청",
    "전북",
    "전라",
    "경북",
    "경상",
    "제주",
    "사는",
    "거주",
)
NEW_TOPIC_KEYWORDS: Tuple[str, ...] = (
    "다른",
    "말고",
    "새로운",
    "새 공고",
    "다시 찾아",
)


def get_or_create_chat_session(
    db: Session,
    *,
    user_id: int,
    session_id: Optional[uuid.UUID],
) -> ChatSession:
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .one_or_none()
        )
        if session is None:
            raise ValueError("대화 세션을 찾을 수 없거나 접근 권한이 없습니다.")
        return session

    session = ChatSession(user_id=user_id)
    db.add(session)
    db.flush()
    return session


def get_recent_chat_messages(
    db: Session,
    session_id: uuid.UUID,
    *,
    limit: int = 6,
) -> List[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def resolve_session_policy_context(
    query: str,
    *,
    session: ChatSession,
    recent_messages: List[ChatMessage],
    selected_policy_id: Optional[uuid.UUID] = None,
) -> Optional[uuid.UUID]:
    """후속 질문일 때만 세션의 선택 공고를 상세 RAG 범위로 쓴다.

    새 정책을 찾는 질문까지 이전 공고로 고정하지 않도록 '다른/말고/새로운'은
    전역 검색으로 되돌린다. 대화 이력이 없으면 오래된 세션의 선택값도 사용하지 않는다.
    """
    active_policy_id = session.active_policy_id or selected_policy_id
    if active_policy_id is None:
        return None
    if selected_policy_id is None and not any(message.role == "user" for message in recent_messages):
        return None

    normalized_query = _normalize_space(query).lower()
    if any(keyword in normalized_query for keyword in NEW_TOPIC_KEYWORDS):
        return None
    if any(keyword in normalized_query for keyword in FOLLOW_UP_CONTEXT_KEYWORDS):
        return active_policy_id

    intent_tags = infer_intent_tags(None, None, query)
    has_generic_attribute_question = any(
        keyword in normalized_query for keyword in GENERIC_POLICY_ATTRIBUTE_KEYWORDS
    ) or any(
        tag in intent_tags
        for tag in ("eligibility", "target", "requirements", "documents", "deadline", "contact")
    )
    if has_generic_attribute_question and (selected_policy_id is not None or len(normalized_query) <= 24):
        return active_policy_id

    return None


def _message_candidates(message: ChatMessage) -> List[Dict[str, Any]]:
    candidates = message.candidates
    return candidates if isinstance(candidates, list) else []


def latest_recommendation_candidates(recent_messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    """최근 맞춤 추천 결과를 반환한다."""
    for message in reversed(recent_messages):
        if message.role != "assistant" or message.response_mode != "recommendation":
            continue
        candidates = _message_candidates(message)
        if candidates:
            return candidates
    return []


def is_recommendation_follow_up_question(
    query: str,
    recent_messages: List[ChatMessage],
) -> bool:
    """추천 결과에 대한 이의제기/설명 요청인지 판단한다."""
    if not latest_recommendation_candidates(recent_messages):
        return False

    normalized_query = _normalize_space(query).lower()
    if not normalized_query:
        return False

    has_recommendation_signal = any(
        keyword in normalized_query for keyword in RECOMMENDATION_FOLLOW_UP_KEYWORDS
    )
    has_reason_or_challenge = any(
        keyword in normalized_query
        for keyword in ("왜", "이유", "근거", "맞아", "아니", "다른", "지역", "사는", "거주")
    )
    return has_recommendation_signal and has_reason_or_challenge


def build_conversation_context(recent_messages: List[ChatMessage], *, limit: int = 6) -> str:
    """LLM 프롬프트에 넣을 짧은 대화 요약을 만든다."""
    blocks: List[str] = []
    for message in recent_messages[-limit:]:
        role_label = {
            "user": "사용자",
            "assistant": "챗봇",
            "system": "시스템",
        }.get(message.role, message.role)
        content = _normalize_space(message.content)
        if len(content) > 240:
            content = f"{content[:240].rstrip()}..."
        if content:
            blocks.append(f"{role_label}: {content}")

        candidates = _message_candidates(message)
        if candidates:
            titles = [
                str(candidate.get("title") or candidate.get("policy_title") or "").strip()
                for candidate in candidates[:3]
            ]
            titles = [title for title in titles if title]
            if titles:
                blocks.append(f"추천/검색 후보: {', '.join(titles)}")

            profile_region = candidates[0].get("profile_region") if isinstance(candidates[0], dict) else None
            if isinstance(profile_region, dict):
                region_text = " ".join(
                    str(value)
                    for value in [profile_region.get("sido"), profile_region.get("sigungu")]
                    if value
                )
                if region_text:
                    blocks.append(f"사용자 프로필 지역: {region_text}")

    return "\n".join(blocks)


def build_recommendation_follow_up_answer(
    query: str,
    recent_messages: List[ChatMessage],
) -> Optional[str]:
    """최근 추천 결과를 근거로 추천 관련 후속 질문에 답한다."""
    candidates = latest_recommendation_candidates(recent_messages)
    if not candidates or not is_recommendation_follow_up_question(query, recent_messages):
        return None

    profile_region = candidates[0].get("profile_region") if isinstance(candidates[0], dict) else None
    region_text = ""
    if isinstance(profile_region, dict):
        region_text = " ".join(
            str(value)
            for value in [profile_region.get("sido"), profile_region.get("sigungu")]
            if value
        )

    lines = [
        "직전에 추천한 결과를 기준으로 다시 볼게요.",
    ]
    if region_text:
        lines.append(f"현재 저장된 사용자 지역은 `{region_text}`입니다.")

    normalized_query = _normalize_space(query).lower()
    asks_region = any(keyword in normalized_query for keyword in ("서울", "경기", "경기도", "지역", "사는", "거주"))
    if asks_region:
        lines.extend(
            [
                "",
                "추천 결과에 다른 지역 정책이 보였다면, 보통 아래 둘 중 하나예요.",
                "- 해당 정책의 지역 조건이 `전국` 또는 `지역 확인 필요`로 분류되어 후보에 남은 경우",
                "- 원문에서 지역 조건을 확실히 추출하지 못해 `확인 필요` 후보로 남은 경우",
            ]
        )

    lines.append("")
    lines.append("최근 추천 후보는 다음과 같아요.")
    for index, candidate in enumerate(candidates[:3], start=1):
        title = candidate.get("title") or candidate.get("policy_title") or "정책명 확인 필요"
        match_status = candidate.get("match_status") or candidate.get("eligibility_status") or "확인 필요"
        reasons = candidate.get("reasons") or []
        warnings = candidate.get("warnings") or []
        line = f"{index}. {title} — 판정: {match_status}"
        if reasons:
            line += f" / 이유: {reasons[0]}"
        elif warnings:
            line += f" / 확인: {warnings[0]}"
        lines.append(line)

    lines.extend(
        [
            "",
            "정확도를 높이려면 추천 화면에서 `적합`만 필터링하거나, 채팅에 `서울 기준으로 다시 추천해줘`처럼 말해 주세요. "
            "특정 정책을 누른 뒤에는 그 정책 공고문 기준으로 대상·서류·기간을 이어서 답할게요.",
        ]
    )
    return "\n".join(lines)


def record_recommendation_turn(
    db: Session,
    *,
    session: ChatSession,
    profile_region: Dict[str, Any],
    results: List[Any],
    source_query: str = "맞춤 정책 추천해줘",
    profile_warnings: Optional[List[str]] = None,
    limit: int = 5,
) -> None:
    """추천 API 결과를 채팅 이력에 저장해 후속 질문이 직전 추천 맥락을 알 수 있게 한다."""
    candidates: List[Dict[str, Any]] = []
    for item in results[:limit]:
        candidates.append(
            {
                "policy_id": str(getattr(item, "policy_id", "")),
                "title": getattr(item, "title", None),
                "summary": getattr(item, "summary", None),
                "support_type": getattr(item, "support_type", None),
                "match_status": getattr(item, "match_status", None),
                "eligibility_status": getattr(item, "eligibility_status", None),
                "preference_match": getattr(item, "preference_match", None),
                "reasons": list(getattr(item, "reasons", []) or []),
                "warnings": list(getattr(item, "warnings", []) or []),
                "unmet_conditions": list(getattr(item, "unmet_conditions", []) or []),
                "matched_tags": dict(getattr(item, "matched_tags", {}) or {}),
                "profile_region": profile_region,
            }
        )

    db.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content=source_query,
            response_mode="recommendation_request",
        )
    )
    db.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=(
                "프로필 기준 맞춤 정책 추천 결과"
                + (
                    f"\n입력 정보 확인: {' / '.join(profile_warnings[:2])}"
                    if profile_warnings
                    else ""
                )
            ),
            response_mode="recommendation",
            candidates=candidates or None,
        )
    )
    session.active_policy_id = None
    session.updated_at = func.now()
    db.commit()


def record_chat_turn(
    db: Session,
    *,
    session: ChatSession,
    query: str,
    answer: str,
    response_mode: str,
    context_policy_id: Optional[uuid.UUID],
    candidates: List[Dict[str, Any]],
    sources: Optional[List[Dict[str, Any]]] = None,
) -> None:
    db.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content=query,
            policy_id=context_policy_id,
        )
    )
    db.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            policy_id=context_policy_id,
            response_mode=response_mode,
            candidates=candidates or None,
            sources=sources or None,
        )
    )
    session.updated_at = func.now()
    db.commit()


def retrieve_policy_document_sources(
    db: Session,
    query: str,
    *,
    policy_id: uuid.UUID,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """정책이 정해진 채팅은 임베딩 없이 부모 문서 전체에서 근거를 고른다."""
    if is_out_of_policy_scope(query, policy_id=policy_id):
        return {
            "query": query,
            "expanded_query": query,
            "intent_tags": ["out_of_scope"],
            "response_mode": "out_of_scope",
            "candidates": [],
            "sources": [],
        }

    policy = (
        db.query(NormalizedPolicy)
        .filter(NormalizedPolicy.id == policy_id)
        .one_or_none()
    )
    if policy is None:
        return {
            "query": query,
            "expanded_query": query,
            "intent_tags": ["general"],
            "response_mode": "no_result",
            "candidates": [],
            "sources": [],
        }

    documents = (
        db.query(PolicyDocument)
        .filter(PolicyDocument.policy_id == policy_id)
        .order_by(PolicyDocument.created_at.asc(), PolicyDocument.id.asc())
        .all()
    )
    intent_tags = infer_intent_tags(None, None, query)
    primary_intent = _primary_attribute_intent(intent_tags)
    target_document_types = (
        _document_types_for_intents([primary_intent])
        if primary_intent
        else ()
    )

    selected_documents = [
        document
        for document in documents
        if document.document_type in target_document_types
    ]
    if target_document_types and not selected_documents:
        # 구비 서류처럼 별도 문서가 생성되지 않은 경우에는 전체 항목이 보존된
        # body/section 부모 문서를 LLM 근거로 사용한다.
        selected_documents = [
            document
            for document in documents
            if document.document_type in ("body", "section")
        ]
    if not selected_documents:
        selected_documents = documents

    requested_limit = limit or settings.CHAT_RETRIEVAL_LIMIT
    sources = [
        policy_document_to_source(policy, document)
        for document in selected_documents[:requested_limit]
        if _normalize_space(document.text)
    ]
    return {
        "query": query,
        "expanded_query": query,
        "intent_tags": intent_tags,
        "response_mode": "answer" if sources else "no_result",
        "candidates": [],
        "sources": sources,
    }


def retrieve_policy_chunk_sources(
    db: Session,
    query: str,
    *,
    limit: Optional[int] = None,
    policy_id: Optional[uuid.UUID] = None,
    embedding_model: Optional[EmbeddingModel] = None,
    model_mode: str | None = None,
) -> Dict[str, Any]:
    if is_out_of_policy_scope(query, policy_id=policy_id):
        return {
            "query": query,
            "expanded_query": query,
            "intent_tags": ["out_of_scope"],
            "response_mode": "out_of_scope",
            "candidates": [],
            "sources": [],
        }

    selected_mode = normalize_model_mode(model_mode)
    if selected_mode is None:
        selected_mode = (
            "local"
            if settings.CHAT_EMBEDDING_PROVIDER.strip().lower() == "ollama"
            else "cloud"
        )
    model = embedding_model or get_embedding_model("chat", model_mode=selected_mode)
    vector_column = (
        PolicyChunk.embedding_ollama
        if selected_mode == "local"
        else PolicyChunk.embedding_openai
    )
    expanded_query = build_query_embedding_text(query, policy_id=policy_id)
    intent_tags = infer_intent_tags(None, None, query)
    requested_limit = limit or settings.CHAT_RETRIEVAL_LIMIT
    results = search_policy_chunks(
        db=db,
        query=expanded_query,
        embedding_model=model,
        limit=max(requested_limit * 4, requested_limit),
        policy_id=policy_id,
        embedding_column=vector_column,
    )
    sources = [
        source
        for source in (chunk_to_source(chunk, similarity) for chunk, similarity in results)
        if _normalize_space(str(source.get("chunk_text") or ""))
    ]
    sources = rerank_sources_by_intent(
        sources,
        intent_tags,
        prefer_small_business_domain=policy_id is None,
    )[:requested_limit]
    if not sources:
        return {
            "query": query,
            "expanded_query": expanded_query,
            "intent_tags": intent_tags,
            "response_mode": "no_result",
            "candidates": [],
            "sources": [],
        }

    candidates = build_policy_candidates(sources) if policy_id is None else []
    response_mode = "answer"
    if should_request_policy_selection(
        query,
        intent_tags,
        candidates,
        policy_id=policy_id,
    ):
        response_mode = "policy_selection"

    sources = attach_neighbor_context(
        db,
        sources,
        window=settings.CHAT_NEIGHBOR_CHUNK_WINDOW,
    )
    return {
        "query": query,
        "expanded_query": expanded_query,
        "intent_tags": intent_tags,
        "response_mode": response_mode,
        "candidates": candidates if response_mode == "policy_selection" else [],
        "sources": sources,
    }


def attach_neighbor_context(
    db: Session,
    sources: List[Dict[str, Any]],
    *,
    window: int = 1,
) -> List[Dict[str, Any]]:
    """검색 청크의 앞뒤 청크를 답변용 문맥에만 덧붙입니다.

    사용자에게 보여주는 source/chunk_text는 검색된 원문 그대로 유지하고,
    답변 프롬프트를 만들 때만 같은 문서의 인접 청크를 함께 사용합니다.
    """
    if not sources or window <= 0:
        return sources

    document_ids = {source.get("document_id") for source in sources if source.get("document_id")}
    if not document_ids:
        return sources

    try:
        parsed_document_ids = [uuid.UUID(str(value)) for value in document_ids]
        chunk_rows = (
            db.query(PolicyChunk)
            .filter(PolicyChunk.document_id.in_(parsed_document_ids))
            .all()
        )
    except (ValueError, TypeError):
        return sources

    by_document: Dict[uuid.UUID, Dict[int, str]] = {}
    for row in chunk_rows:
        cleaned_text = clean_rag_answer_text(row.chunk_text)
        if cleaned_text:
            by_document.setdefault(row.document_id, {})[row.chunk_index] = cleaned_text

    for source in sources:
        try:
            document_id = uuid.UUID(str(source["document_id"]))
            chunk_index = int(source["chunk_index"])
        except (KeyError, ValueError, TypeError):
            continue

        chunks = by_document.get(document_id, {})
        context = [
            chunks[index]
            for index in range(chunk_index - window, chunk_index + window + 1)
            if index in chunks
        ]
        if context:
            source["retrieval_context"] = "\n".join(context)

    return sources


def build_context_text(sources: List[Dict[str, Any]]) -> str:
    blocks = []
    total_chars = 0
    for index, source in enumerate(sources, start=1):
        metadata = source.get("metadata") or {}
        context_body = clean_rag_answer_text(source.get("retrieval_context")) or source_answer_text(source)
        if not context_body:
            continue
        region = " ".join(
            str(value)
            for value in [metadata.get("sido"), metadata.get("sigungu")]
            if value
        ) or ("전국" if metadata.get("region_scope") == "national" else "확인 필요")
        application_methods = ", ".join(metadata.get("application_methods") or [])
        content_label = (
            "선택된 부모 문서 전체 원문"
            if metadata.get("retrieval_mode") == "parent_document"
            else "검색 청크 및 인접 문맥"
        )
        block = (
            f"[근거 {index}]\n"
            f"정책명: {source.get('policy_title')}\n"
            f"기관: {metadata.get('organization')}\n"
            f"지원유형: {metadata.get('support_type')}\n"
            f"신청상태: {metadata.get('status')}\n"
            f"대상지역: {region}\n"
            f"문서유형: {source.get('document_type')}\n"
            f"문서제목: {source.get('document_title')}\n"
            f"신청기간: {source.get('apply_start')} ~ {source.get('apply_end')}\n"
            f"신청방법: {application_methods or '확인 필요'}\n"
            f"문의처: {', '.join(source.get('contact_points') or [])}\n"
            f"예상질문태그: {', '.join(metadata.get('intent_tags') or [])}\n"
            f"내용({content_label}): {context_body}\n"
        )
        if total_chars + len(block) > settings.CHAT_MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total_chars += len(block)
    return "\n".join(blocks)


FOCUSED_FALLBACK_SECTIONS: Dict[str, Tuple[str, ...]] = {
    "eligibility": ("지원 대상", "지원대상", "신청 대상", "신청대상", "대상"),
    "target": ("지원 대상", "지원대상", "신청 대상", "신청대상", "대상"),
    "requirements": ("구비 서류", "구비서류", "필요 서류", "필요서류", "제출 서류", "제출서류"),
    "documents": ("구비 서류", "구비서류", "필요 서류", "필요서류", "제출 서류", "제출서류"),
    "application": ("신청 방법", "신청방법", "접수 방법", "접수방법", "신청"),
    "apply_method": ("신청 방법", "신청방법", "접수 방법", "접수방법", "신청"),
    "deadline": ("신청 기한", "신청기한", "신청 기간", "신청기간", "접수 기간", "접수기간", "마감"),
    "schedule": ("신청 기한", "신청기한", "신청 기간", "신청기간", "접수 기간", "접수기간", "마감"),
    "contact": ("문의처", "문의", "담당 기관", "담당기관", "접수처"),
    "benefit": ("지원 내용", "지원내용", "혜택", "지원 금액", "지원금액"),
    "support_content": ("지원 내용", "지원내용", "혜택", "지원 금액", "지원금액"),
}


SECTION_LABEL_PATTERN = re.compile(r"\[([^\[\]]{1,30})\]")


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \n\t:-")


STRUCTURED_JSON_NOISE_KEYS: Tuple[str, ...] = (
    "business_age_limit",
    "employee_limit",
    "sales_limit",
    "constraints",
    "operator",
    "source_text",
    "unit",
    "value",
    "logic",
    "requires_manual_review",
    "review_reason",
    "extraction_method",
)
STRUCTURED_JSON_NOISE_PATTERN = re.compile(
    r'"(?:business_age_limit|employee_limit|sales_limit|constraints|operator|source_text|unit|value|logic|requires_manual_review|review_reason|extraction_method)"\s*:'
)


def _source_text_values_from_json_noise(value: str) -> List[str]:
    return _dedupe_preserve_order(
        _normalize_space(match.group(1))
        for match in re.finditer(r'"source_text"\s*:\s*"([^"]+)"', value)
        if _normalize_space(match.group(1))
    )


def _is_structured_json_noise_line(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if STRUCTURED_JSON_NOISE_PATTERN.search(stripped):
        return True
    if not any(key in stripped for key in STRUCTURED_JSON_NOISE_KEYS):
        return False
    json_marks = sum(stripped.count(mark) for mark in ('"', "{", "}", "[", "]", ":"))
    return stripped.startswith(("{", "}", "[", "]", '"', ",")) or json_marks >= 4


def clean_rag_display_text(value: Any) -> str:
    """사용자 답변/근거에 노출할 RAG 텍스트에서 정규화용 JSON 찌꺼기를 제거한다."""
    if value is None:
        return ""

    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    source_text_values = _source_text_values_from_json_noise(text)
    kept_lines: List[str] = []
    for line in text.split("\n"):
        if _is_structured_json_noise_line(line):
            continue
        kept_lines.append(line)

    cleaned = _normalize_space("\n".join(kept_lines))
    if cleaned and source_text_values:
        existing = cleaned
        missing_values = [item for item in source_text_values if item not in existing]
        if missing_values:
            cleaned = _normalize_space(f"{cleaned} {' '.join(missing_values)}")
    elif not cleaned and source_text_values:
        cleaned = " / ".join(source_text_values)

    if _is_structured_json_noise_line(cleaned) and not source_text_values:
        return ""
    return cleaned


INTERNAL_JUDGEMENT_PREFIX_PATTERN = re.compile(
    r"^\s*(?:[-•]\s*)?(?:여부\s*)?판단\s*\d{0,3}\s*"
)


def clean_rag_evidence_text(value: Any) -> str:
    """답변 근거 카드에 표시할 텍스트를 사람이 읽기 쉬운 형태로 가공한다."""
    display_text = clean_rag_display_text(value)
    if not display_text:
        return ""

    if "판단" not in display_text:
        return display_text

    cleaned = INTERNAL_JUDGEMENT_PREFIX_PATTERN.sub("", display_text).strip()
    if not cleaned:
        return ""

    cleaned = re.sub(
        r"\(([^)]*?)-([^)]*?)\)",
        lambda match: f"({match.group(1).strip()} {match.group(2).strip()})",
        cleaned,
    )
    cleaned = re.sub(r"^([^:：]{2,40})\s+\(([^)]{2,60})\)\s+(.+)$", r"\1: \2, \3", cleaned)
    return _normalize_space(cleaned)


ANSWER_ONLY_ADMIN_LINE_PATTERN = re.compile(
    r"^\s*(?:[-•]\s*)?(?:여부\s*)?판단\s*\d{0,3}\b.*$"
)
ANSWER_CONDITION_ANCHOR_PATTERN = re.compile(
    r"(?:\d+\s*(?:인|명|억원|만원|원|년)\s*(?:미만|이하|이상|초과)|상시\s*근로자|소상공인기본법|제조업|건설업|운수업|업체|사업자|매출|업력)"
)


def clean_rag_answer_text(value: Any) -> str:
    """채팅 답변 본문/LLM 프롬프트에서는 내부 판정 절차 문구를 빼고 조건만 남긴다."""
    display_text = clean_rag_display_text(value)
    if not display_text:
        return ""

    if "여부 판단" in display_text:
        condition_start = ANSWER_CONDITION_ANCHOR_PATTERN.search(display_text)
        if condition_start:
            display_text = display_text[condition_start.start():]

    kept_lines: List[str] = []
    for line in display_text.split("\n"):
        normalized_line = _normalize_space(line)
        if not normalized_line:
            continue
        if ANSWER_ONLY_ADMIN_LINE_PATTERN.match(normalized_line):
            continue
        kept_lines.append(normalized_line)

    return _normalize_space("\n".join(kept_lines))


def source_answer_text(source: Dict[str, Any]) -> str:
    if source.get("answer_text") is not None:
        return clean_rag_answer_text(source.get("answer_text"))
    return clean_rag_answer_text(source.get("raw_chunk_text") or source.get("chunk_text"))


POLICY_DOMAIN_KEYWORDS: Tuple[str, ...] = (
    "정책",
    "공고",
    "공고문",
    "복지",
    "지원",
    "지원금",
    "현금",
    "현금성",
    "지급",
    "장려금",
    "급여",
    "혜택",
    "보조금",
    "융자",
    "대출",
    "보증",
    "소상공인",
    "사업자",
    "사업장",
    "업종",
    "매출",
    "직원",
    "신청",
    "접수",
    "서류",
    "대상",
    "자격",
    "요건",
    "조건",
    "해당",
    "받을 수",
    "마감",
    "기간",
    "문의",
    "기관",
    "지역",
    "노란우산",
    "손실보상",
    "전기요금",
    "냉난방",
)


DETAIL_CONTEXT_KEYWORDS: Tuple[str, ...] = (
    "이거",
    "여기",
    "이 정책",
    "이 공고",
    "요약",
    "정리",
    "설명",
    "필요",
    "준비",
    "언제",
    "어디",
    "누구",
    "얼마",
    "방법",
    "기간",
    "서류",
    "대상",
    "문의",
    "마감",
    "조건",
    "자격",
    "해당",
    "가능",
    "받을 수",
)


OUT_OF_SCOPE_KEYWORDS: Tuple[str, ...] = (
    "날씨",
    "기온",
    "습도",
    "미세먼지",
    "강수",
    "비와",
    "비 와",
    "눈와",
    "눈 와",
    "더워",
    "더운",
    "덥냐",
    "추워",
    "추운",
    "춥냐",
    "우산 챙",
    "우산 가져",
    "점심",
    "저녁",
    "아침 뭐",
    "뭐 먹",
    "맛집",
    "머리",
    "단발",
    "기를까",
    "길러",
    "염색",
    "파마",
    "헤어",
    "미용실",
    "옷",
    "입을까",
    "코디",
    "연애",
    "남친",
    "여친",
    "고백",
    "이별",
    "잠",
    "졸려",
    "피곤",
    "농담",
    "노래",
    "영화",
    "드라마",
    "스포츠",
    "연예",
    "주식",
    "비트코인",
    "환율",
    "코딩",
    "파이썬",
    "자바스크립트",
)


WEATHER_KEYWORDS: Tuple[str, ...] = (
    "날씨",
    "기온",
    "습도",
    "미세먼지",
    "강수",
    "비와",
    "비 와",
    "눈와",
    "눈 와",
    "더워",
    "추워",
    "우산 챙",
    "우산 가져",
)


def is_out_of_policy_scope(query: str, *, policy_id: Optional[uuid.UUID] = None) -> bool:
    normalized = _normalize_space(query).lower()
    if not normalized:
        return False

    has_policy_signal = any(keyword in normalized for keyword in POLICY_DOMAIN_KEYWORDS)
    has_detail_context_signal = policy_id is not None and any(
        keyword in normalized for keyword in DETAIL_CONTEXT_KEYWORDS
    )
    has_out_of_scope_signal = any(keyword in normalized for keyword in OUT_OF_SCOPE_KEYWORDS)

    if has_out_of_scope_signal and not has_policy_signal:
        return True

    if has_policy_signal or has_detail_context_signal:
        return False

    # RAG는 항상 뭔가를 찾아내므로, 정책 신호가 전혀 없는 일반 질문은 검색하지 않는다.
    # 예: "나 머리 단발할까 기를까", "오늘 기분이 별로야", "뭐 하지?"
    return True


def build_out_of_scope_answer(query: str) -> str:
    normalized = _normalize_space(query).lower()
    if any(keyword in normalized for keyword in WEATHER_KEYWORDS):
        return (
            "날씨는 제가 정확히 확인해드릴 수 없어요. "
            "저는 소상공인 정책 공고를 기준으로 지원 대상, 신청 기간, 필요 서류, 접수 방법을 안내하는 챗봇이에요.\n\n"
            "정책과 관련해서 궁금한 내용을 물어보면 공고문 근거로 바로 찾아드릴게요."
        )
    return (
        "저는 소상공인 정책 공고를 안내하는 챗봇이라 이 질문에는 정확히 답하기 어려워요.\n\n"
        "지원 대상, 신청 기간, 필요 서류, 접수 방법처럼 정책과 관련된 질문을 해주시면 공고문 근거로 답변해드릴게요."
    )


def _extract_bracket_sections(text: str) -> Dict[str, str]:
    matches = list(SECTION_LABEL_PATTERN.finditer(text))
    sections: Dict[str, str] = {}
    for index, match in enumerate(matches):
        label = _normalize_space(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = _normalize_space(text[start:end])
        if label and content:
            sections.setdefault(label, content)
    return sections


def _section_value_for_intents(text: str, intents: Iterable[str]) -> Optional[str]:
    sections = _extract_bracket_sections(text)
    if not sections:
        return None

    for intent in intents:
        for wanted_label in FOCUSED_FALLBACK_SECTIONS.get(intent, ()):
            for label, content in sections.items():
                normalized_label = label.replace(" ", "")
                normalized_wanted = wanted_label.replace(" ", "")
                if normalized_label == normalized_wanted or normalized_wanted in normalized_label:
                    return content
    return None


def _fallback_points(value: str, limit: int = 5) -> List[str]:
    cleaned = _normalize_space(value)
    if not cleaned:
        return []
    if cleaned in {"해당없음", "해당 없음", "없음", "없습니다"}:
        return [cleaned]

    # 일반 쉼표는 목록 구분자로 사용하되 4,500만원처럼 숫자 사이의 천 단위
    # 쉼표는 보존한다.
    pieces = re.split(r"\s*(?:\|\||ㆍ|•|(?<!\d),(?!\d)|;| 또는 | 혹은 )\s*", cleaned)
    points = [_normalize_space(piece) for piece in pieces if _normalize_space(piece)]
    return _dedupe_preserve_order(points)[:limit] or [cleaned]


def _friendly_heading(intent_tags: List[str]) -> str:
    if any(tag in intent_tags for tag in ("requirements", "documents")):
        return "필요한 서류는 다음과 같아요."
    if any(tag in intent_tags for tag in ("application", "apply_method")):
        return "신청 방법은 다음과 같아요."
    if any(tag in intent_tags for tag in ("deadline", "schedule")):
        return "신청 기간은 다음과 같아요."
    if "contact" in intent_tags:
        return "문의처는 다음과 같아요."
    if any(tag in intent_tags for tag in ("eligibility", "target")):
        return "지원 대상은 다음과 같아요."
    if any(tag in intent_tags for tag in ("benefit", "support_content")):
        return "지원 내용은 다음과 같아요."
    return "공고문에서 확인한 내용이에요."


DIRECT_DOCUMENT_TYPE_BY_INTENT: Dict[str, Tuple[str, ...]] = {
    "eligibility": ("eligibility",),
    "target": ("eligibility",),
    "requirements": ("requirements",),
    "documents": ("requirements",),
    "application": ("application", "procedure"),
    "apply_method": ("application", "procedure"),
    "deadline": ("deadline",),
    "schedule": ("deadline",),
    "contact": ("contact",),
    "benefit": ("support_content", "summary"),
    "support_content": ("support_content", "summary"),
}

DIRECT_INTENT_PRIORITY: Tuple[Tuple[str, ...], ...] = (
    ("requirements", "documents"),
    ("deadline", "schedule"),
    ("contact",),
    ("application", "apply_method"),
    ("eligibility", "target"),
    ("benefit", "support_content"),
)

ATTRIBUTE_ANSWER_INTENTS: Tuple[str, ...] = (
    "eligibility",
    "target",
    "requirements",
    "documents",
    "application",
    "apply_method",
    "deadline",
    "schedule",
    "contact",
)

PLAIN_LANGUAGE_ANSWER_INSTRUCTION = (
    "일반인이 한 번에 이해할 수 있도록 중학생도 이해할 수 있는 쉬운 한국어로 설명해라. "
    "법률명·행정용어·전문용어만 그대로 반복하지 말고, 쉬운 뜻을 먼저 말한 뒤 "
    "필요한 경우에만 원문 용어를 괄호 안에 덧붙여라. "
    "예를 들어 '「소상공인기본법」에 따른 소상공인'은 "
    "'직원 수와 매출 규모 등이 법에서 정한 소상공인 기준에 맞는 작은 사업체'처럼 풀어 설명해라. "
    "'융자'는 '정책자금 대출', '융자제외업종'은 "
    "'정책자금 대출을 받을 수 없도록 정해진 업종', '구비서류'는 '준비할 서류', "
    "'업력'은 '사업을 운영한 기간', '영위'는 '운영', "
    "'상시근로자'는 '평소 계속 고용한 직원', '선정기준'은 '지원 대상을 뽑는 기준', "
    "'소관기관'은 '담당 기관'처럼 바꿔라. "
    "다만 검색 근거에 구체적인 직원 수·매출 기준이 없으면 숫자를 만들지 말고, "
    "업종에 따라 기준이 다를 수 있어 공고나 담당 기관 확인이 필요하다고 알려라."
)


def _primary_attribute_intent(intent_tags: Iterable[str]) -> Optional[str]:
    """질문에 여러 키워드가 있어도 가장 구체적인 단일 답변 항목을 고른다."""
    tag_set = set(intent_tags)
    for priority_group in DIRECT_INTENT_PRIORITY:
        for intent in priority_group:
            if intent in tag_set:
                return intent
    return None

REQUIREMENT_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"사업자등록증\s*사본", "사업자등록증 사본"),
    (r"사업자등록증", "사업자등록증"),
    (r"금융거래사실확인서", "금융거래사실확인서"),
    (r"최근\s*3년간\s*재무제표", "최근 3년간 재무제표"),
    (r"부동산등기부등본", "부동산등기부등본"),
    (r"사업장\s*및\s*거주주택\s*임차계약서", "사업장 및 거주주택 임차계약서"),
    (r"사업장\s*임차계약서", "사업장 임차계약서"),
    (r"거주주택\s*임차계약서", "거주주택 임차계약서"),
    (r"임대차\s*계약서", "임대차 계약서"),
    (r"임차계약서", "임차계약서"),
    (r"소상공인\s*확인서", "소상공인 확인서"),
    (r"매출\s*증빙(?:서류)?", "매출 증빙서류"),
    (r"납세증명서", "납세증명서"),
    (r"지방세\s*납세증명서", "지방세 납세증명서"),
    (r"통장\s*사본", "통장 사본"),
    (r"신분증", "신분증"),
    (r"신청서", "신청서"),
)


def _strip_requirement_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:구비\s*서류|구비서류|필요\s*서류|필요서류|제출\s*서류|제출서류)\s*[:：]\s*",
        "",
        _normalize_space(text),
    )


def _requirement_points(text: str) -> List[str]:
    cleaned = _strip_requirement_prefix(text)
    if not cleaned:
        return []

    if re.search(r"\|\||ㆍ|•|(?<!\d),(?!\d)|;| 또는 | 혹은 ", cleaned):
        return _fallback_points(cleaned)

    matches: List[Tuple[int, int, str]] = []
    for pattern, label in REQUIREMENT_PATTERNS:
        for match in re.finditer(pattern, cleaned):
            matches.append((match.start(), match.end(), label))

    if matches:
        selected: List[Tuple[int, int, str]] = []
        for start, end, label in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
            if any(start < selected_end and end > selected_start for selected_start, selected_end, _ in selected):
                continue
            selected.append((start, end, label))
        return _dedupe_preserve_order(label for _, _, label in selected)

    return _fallback_points(cleaned)


def _document_types_for_intents(intent_tags: Iterable[str]) -> Tuple[str, ...]:
    tag_set = set(intent_tags)
    document_types: List[str] = []
    for priority_group in DIRECT_INTENT_PRIORITY:
        if not tag_set.intersection(priority_group):
            continue
        for intent in priority_group:
            document_types.extend(DIRECT_DOCUMENT_TYPE_BY_INTENT.get(intent, ()))
        break
    return tuple(_dedupe_preserve_order(document_types))


def _render_focused_attribute_answer(
    policy_title: str,
    intent_tags: List[str],
    points: Iterable[str],
) -> Optional[str]:
    cleaned_points = _dedupe_preserve_order(
        _normalize_space(point) for point in points if _normalize_space(point)
    )[:8]
    if not cleaned_points:
        return None

    primary_intent = _primary_attribute_intent(intent_tags)
    compact_single = cleaned_points[0].replace(" ", "") if len(cleaned_points) == 1 else ""
    if primary_intent in ("requirements", "documents") and compact_single in {
        "해당없음",
        "없음",
        "없습니다",
    }:
        return f"{policy_title} 기준으로 보면, 별도로 준비해야 하는 서류는 명시되어 있지 않아요."
    if primary_intent in ("deadline", "schedule") and compact_single in {
        "상시신청",
        "상시접수",
    }:
        return f"{policy_title}의 신청 기간은 상시 신청이에요."

    heading = _friendly_heading(intent_tags)
    if len(cleaned_points) == 1:
        return f"{policy_title} 기준으로 보면, {heading}\n\n{cleaned_points[0]}"
    return "\n".join(
        [
            f"{policy_title} 기준으로 보면, {heading}",
            "",
            *[f"- {point}" for point in cleaned_points],
        ]
    )


def build_direct_document_type_answer(
    policy_title: str,
    intent_tags: List[str],
    sources: List[Dict[str, Any]],
) -> Optional[str]:
    target_document_types = _document_types_for_intents(intent_tags)
    if not target_document_types:
        return None

    matched_sources = [
        source
        for source in sources
        if source.get("document_type") in target_document_types and _normalize_space(str(source.get("chunk_text") or ""))
    ]
    if not matched_sources:
        return None

    points: List[str] = []
    for source in matched_sources:
        chunk_text = source_answer_text(source)
        if source.get("document_type") == "requirements":
            points.extend(_requirement_points(chunk_text))
        else:
            points.extend(_fallback_points(chunk_text, limit=3))

    points = _dedupe_preserve_order(points)[:8]
    if not points:
        return None

    return _render_focused_attribute_answer(
        policy_title,
        intent_tags,
        points,
    )


def build_focused_attribute_answer(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    intent_tags: Optional[List[str]] = None,
) -> Optional[str]:
    """대상·서류·기간 등 단일 속성 질문에는 그 속성의 근거만 답한다."""
    if not sources:
        return None

    resolved_intents = intent_tags or infer_intent_tags(None, None, query)
    primary_intent = _primary_attribute_intent(resolved_intents)
    if not primary_intent or primary_intent not in ATTRIBUTE_ANSWER_INTENTS:
        return None
    focused_intents = [primary_intent]

    best_source = sources[0]
    best_policy_id = best_source.get("policy_id")
    scoped_sources = (
        [source for source in sources if source.get("policy_id") == best_policy_id]
        if best_policy_id
        else sources
    )
    policy_title = best_source.get("policy_title") or "이 공고"

    direct_answer = build_direct_document_type_answer(
        policy_title,
        focused_intents,
        scoped_sources,
    )
    if direct_answer:
        return direct_answer

    for source in scoped_sources:
        focused_value = _section_value_for_intents(
            source_answer_text(source),
            focused_intents,
        )
        if not focused_value:
            continue
        return _render_focused_attribute_answer(
            policy_title,
            focused_intents,
            _fallback_points(focused_value),
        )
    return None


def build_retrieval_only_answer(query: str, sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "공고문에서 관련 내용을 찾지 못했어요. 질문을 조금 더 구체적으로 입력해 주세요."

    intent_tags = infer_intent_tags(None, None, query)
    best_source = sources[0]
    policy_title = best_source.get("policy_title") or "이 공고"

    focused_answer = build_focused_attribute_answer(
        query,
        sources,
        intent_tags=intent_tags,
    )
    if focused_answer:
        return focused_answer

    candidate_answer = build_policy_candidate_fallback(query, sources, intent_tags)
    if candidate_answer:
        return candidate_answer

    snippets = _dedupe_preserve_order(
        source_answer_text(source) for source in sources[:3]
    )
    if not snippets:
        return "공고문에서 관련 내용을 찾지 못했어요. 질문을 조금 더 구체적으로 입력해 주세요."

    first_snippet = snippets[0]
    if len(first_snippet) > 420:
        first_snippet = f"{first_snippet[:420].rstrip()}..."
    return (
        f"{policy_title} 공고문에서 가장 가까운 내용을 찾았어요.\n\n"
        f"{first_snippet}\n\n"
        "정확한 대상, 서류, 기간처럼 궁금한 항목을 한 번 더 물어보면 더 좁혀서 답변할게요."
    )


def build_policy_candidate_fallback(
    query: str,
    sources: List[Dict[str, Any]],
    intent_tags: List[str],
) -> Optional[str]:
    del query
    if any(tag in intent_tags for tag in ATTRIBUTE_ANSWER_INTENTS):
        return None
    if not any(tag in intent_tags for tag in ("benefit", "eligibility", "target", "general")):
        return None

    candidates: List[Dict[str, Any]] = []
    seen_policy_ids = set()
    for source in sources:
        policy_id = source.get("policy_id")
        if not policy_id or policy_id in seen_policy_ids:
            continue
        seen_policy_ids.add(policy_id)
        candidates.append(source)
        if len(candidates) >= 3:
            break

    if len(candidates) < 2:
        return None

    lines = [
        "관련성이 높은 소상공인 정책 후보를 찾았어요.",
        "",
    ]
    for index, source in enumerate(candidates, start=1):
        metadata = source.get("metadata") or {}
        title = source.get("policy_title") or "정책명 확인 필요"
        support_type = metadata.get("support_type") or source.get("document_title")
        snippet = source_answer_text(source)
        if len(snippet) > 90:
            snippet = f"{snippet[:90].rstrip()}..."
        suffix = f" ({support_type})" if support_type else ""
        lines.append(f"{index}. {title}{suffix}")
        if snippet:
            lines.append(f"   - 근거: {snippet}")

    lines.extend(
        [
            "",
            "정확한 신청 가능 여부는 사업자 상태, 업종, 지역, 매출 조건에 따라 달라요. "
            "궁금한 정책을 눌러 상세 화면에서 이어서 물어보면 더 정확히 좁혀드릴게요.",
        ]
    )
    return "\n".join(lines)


def build_chat_user_prompt(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    conversation_context: str = "",
) -> str:
    intent_tags = infer_intent_tags(None, None, query)
    primary_intent = _primary_attribute_intent(intent_tags)
    if primary_intent:
        focus_label = _friendly_heading([primary_intent]).rstrip(".")
        answer_scope_instruction = (
            f"사용자가 물은 항목은 '{focus_label}'이다. 이 항목에만 답하고, "
            "신청 대상·방법·기간·서류·문의처 등 다른 항목을 함께 나열하지 마라."
        )
    else:
        answer_scope_instruction = (
            "질문에서 요구한 내용에만 직접 답하고, 사용자가 여러 항목을 요청하지 않았다면 "
            "관련 없는 신청 대상·방법·기간·서류·문의처를 덧붙이지 마라."
        )

    context_text = build_context_text(sources)
    conversation_block = (
        f"이전 대화 맥락:\n{conversation_context}\n\n"
        if conversation_context
        else ""
    )
    return (
        f"{conversation_block}"
        f"사용자 질문:\n{query}\n\n"
        f"검색 근거:\n{context_text}\n\n"
        "위 검색 근거만 사용해서 질문에 바로 답해줘. "
        f"{answer_scope_instruction} "
        f"{PLAIN_LANGUAGE_ANSWER_INSTRUCTION} "
        "원문의 숫자·금액·날짜·AND/OR 조건·제외 조건은 의미를 바꾸거나 생략하지 마라. "
        "원문에 슬래시(/)처럼 논리 관계가 명확하지 않은 기호가 있으면 임의로 '그리고'나 '또는'으로 해석하지 말고 원문 표현을 유지해라. "
        "조건이 둘 이상이면 조건별로 짧은 글머리표를 사용하고, 제외 조건은 마지막에 별도 문장으로 분리해라. "
        "근거에 없는 내용은 추측하거나 보완하지 말고, 원문이 모호하면 단정하지 말고 확인이 필요하다고 말해줘."
    )


def generate_chat_answer(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    conversation_context: str = "",
    model_mode: str | None = None,
) -> str:
    if not sources:
        return "관련 정책 문서 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요."

    answer = get_chat_model("chat", model_mode=model_mode).generate(
        system_prompt=settings.CHAT_SYSTEM_PROMPT,
        user_prompt=build_chat_user_prompt(
            query,
            sources,
            conversation_context=conversation_context,
        ),
        stage="answer_generation",
        source_module=__name__,
        source_function="generate_chat_answer",
        temperature=0.0,
    )
    if not answer:
        raise ModelResponseError("챗봇 모델이 빈 응답을 반환했습니다.")
    return answer


def generate_chat_answer_stream(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    conversation_context: str = "",
    model_mode: str | None = None,
) -> Iterator[str]:
    if not sources:
        yield "관련 정책 문서 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요."
        return

    yield from get_chat_model("chat", model_mode=model_mode).stream(
        system_prompt=settings.CHAT_SYSTEM_PROMPT,
        user_prompt=build_chat_user_prompt(
            query,
            sources,
            conversation_context=conversation_context,
        ),
        stage="answer_generation_stream",
        source_module=__name__,
        source_function="generate_chat_answer_stream",
        temperature=0.0,
    )


def answer_policy_question(
    db: Session,
    query: str,
    *,
    limit: Optional[int] = None,
    policy_id: Optional[uuid.UUID] = None,
    recent_messages: Optional[List[ChatMessage]] = None,
    model_mode: str | None = None,
) -> Dict[str, Any]:
    if policy_id is not None:
        retrieval = retrieve_policy_document_sources(
            db=db,
            query=query,
            limit=limit,
            policy_id=policy_id,
        )
    else:
        retrieval = retrieve_policy_chunk_sources(
            db=db,
            query=query,
            limit=limit,
            policy_id=None,
            model_mode=model_mode,
        )
    response_mode = retrieval.get("response_mode", "answer")
    if response_mode == "out_of_scope":
        answer = build_out_of_scope_answer(query)
    elif response_mode == "policy_selection":
        answer = build_policy_selection_answer(retrieval.get("candidates") or [])
    else:
        # 정책이 특정된 상세/후속 채팅은 부모 문서 전체를 GPT가 읽기 쉽게
        # 가공한다. 메인 검색만 짧은 속성 질문에 결정적 응답을 사용한다.
        focused_answer = None
        if policy_id is None:
            focused_answer = build_focused_attribute_answer(
                query,
                retrieval["sources"],
                intent_tags=retrieval.get("intent_tags") or None,
            )
        answer = focused_answer or generate_chat_answer(
            query,
            retrieval["sources"],
            conversation_context=build_conversation_context(recent_messages or []),
            model_mode=model_mode,
        )
    return {**retrieval, "answer": answer}
