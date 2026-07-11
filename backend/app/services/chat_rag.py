import os
import uuid
import hashlib
from functools import wraps
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rag_utils import (
    EmbeddingModel,
    SimpleTextSplitter,
    create_embedding_model,
    search_policy_chunks,
)
from app.models.chat import PolicyChunk
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

KEYWORD_INTENTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("eligibility", ("지원대상", "신청대상", "대상자", "자격", "요건", "누가", "받을 수", "가능", "소상공인", "중소기업")),
    ("requirements", ("제출서류", "구비서류", "필요서류", "첨부서류", "서류", "증빙")),
    ("application", ("신청", "접수", "온라인", "방문", "우편", "이메일", "제출")),
    ("deadline", ("마감", "기간", "접수기간", "신청기간", "시작일", "종료일")),
    ("contact", ("문의", "연락처", "전화", "담당자", "접수처", "기관")),
    ("benefit", ("지원내용", "지원금", "혜택", "금액", "보조금", "융자", "교육", "컨설팅")),
    ("region", ("지역", "시도", "시군구", "전국", "서울", "경기", "부산")),
    ("procedure", ("절차", "선정", "평가", "심사", "발표", "선발")),
]

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


def is_langsmith_enabled() -> bool:
    return bool(settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY)


def configure_langsmith_env() -> None:
    if not is_langsmith_enabled():
        return
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY or "")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)


def traceable_if_enabled(name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_langsmith_enabled():
                return func(*args, **kwargs)
            try:
                from langsmith import traceable
            except ImportError:
                return func(*args, **kwargs)
            configure_langsmith_env()
            return traceable(name=name)(func)(*args, **kwargs)

        return wrapper

    return decorator


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


def build_query_embedding_text(query: str) -> str:
    intent_tags = infer_intent_tags(None, None, query)
    hints = build_question_hints(intent_tags)
    if not hints:
        return query
    return f"사용자 질문: {query}\n질문 의도: {', '.join(intent_tags)}\n관련 표현: {', '.join(hints)}"


def ensure_policy_chunk_embedding_dimension(db: Session) -> Dict[str, Any]:
    """
    policy_chunks.embedding 컬럼의 pgvector 차원을 현재 settings.EMBEDDING_DIM에 맞춥니다.
    기존 차원이 다르면 서로 다른 차원의 벡터를 섞을 수 없으므로 policy_chunks를 비운 뒤 컬럼 타입을 변경합니다.
    """
    if not settings.database_url.startswith("postgresql"):
        return {"checked": False, "reason": "non-postgresql database"}

    expected_dim = int(settings.EMBEDDING_DIM)
    if expected_dim <= 0:
        raise ValueError("EMBEDDING_DIM은 양수여야 합니다.")

    current_type = db.execute(
        text(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = 'policy_chunks'
              AND n.nspname = 'public'
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        )
    ).scalar()

    expected_type = f"vector({expected_dim})"
    if current_type == expected_type:
        return {"checked": True, "changed": False, "current_type": current_type}

    before_count = db.query(func.count(PolicyChunk.id)).scalar() or 0
    db.execute(text("DELETE FROM policy_chunks"))
    db.execute(
        text(
            f"ALTER TABLE policy_chunks "
            f"ALTER COLUMN embedding TYPE vector({expected_dim})"
        )
    )
    db.commit()

    return {
        "checked": True,
        "changed": True,
        "previous_type": current_type,
        "current_type": expected_type,
        "deleted_chunks": before_count,
    }


def build_policy_chunks(
    db: Session,
    *,
    policy_id: Optional[uuid.UUID] = None,
    limit: Optional[int] = None,
    force: bool = True,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> Dict[str, Any]:
    embedding_model = create_embedding_model(provider=provider, model_name=model_name)
    schema_result = ensure_policy_chunk_embedding_dimension(db)
    selected_provider = (provider or settings.CHAT_EMBEDDING_PROVIDER).lower()
    selected_model = model_name or settings.CHAT_EMBEDDING_MODEL
    model_name_log = f"{selected_provider}:{selected_model}"

    query = (
        db.query(PolicyDocument)
        .join(PolicyDocument.policy)
        .filter(PolicyDocument.text.isnot(None))
        .order_by(PolicyDocument.created_at.asc(), PolicyDocument.id.asc())
    )
    if policy_id:
        query = query.filter(PolicyDocument.policy_id == policy_id)
    if not force:
        query = (
            query.outerjoin(PolicyChunk, PolicyChunk.document_id == PolicyDocument.id)
            .filter(PolicyChunk.id.is_(None))
        )
    if limit:
        query = query.limit(limit)

    documents = query.all()
    actual_chunk_size = chunk_size or settings.CHAT_CHUNK_SIZE
    actual_chunk_overlap = chunk_overlap or settings.CHAT_CHUNK_OVERLAP
    stats: Dict[str, Any] = {
        "embedding_model": model_name_log,
        "chunk_size": actual_chunk_size,
        "chunk_overlap": actual_chunk_overlap,
        "force": force,
        "schema": schema_result,
        "target_documents": len(documents),
        "embedded_documents": 0,
        "failed_documents": 0,
        "created_chunks": 0,
        "failures": [],
    }

    splitter = SimpleTextSplitter(chunk_size=actual_chunk_size, chunk_overlap=actual_chunk_overlap)
    prepared_chunks: List[Dict[str, Any]] = []

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

            for chunk_index, (chunk_text, chunk_hash) in enumerate(document_chunks):
                prepared_chunks.append(
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
                            "embedding_input_strategy": "document_context_plus_chunk",
                        },
                        "embedding_input": f"{embedding_context}\n본문: {chunk_text}",
                    }
                )

            if document_chunks:
                stats["embedded_documents"] += 1
                stats["created_chunks"] += len(document_chunks)
        except Exception as exc:
            db.rollback()
            stats["failed_documents"] += 1
            stats["failures"].append(
                {
                    "document_id": str(document.id),
                    "policy_id": str(document.policy_id),
                    "error": str(exc),
                }
            )

    if not prepared_chunks:
        return stats

    try:
        document_ids = list({item["document_id"] for item in prepared_chunks})
        if document_ids:
            (
                db.query(PolicyChunk)
                .filter(PolicyChunk.document_id.in_(document_ids))
                .delete(synchronize_session=False)
            )
            db.flush()

        batch_size = 100
        for start in range(0, len(prepared_chunks), batch_size):
            batch = prepared_chunks[start:start + batch_size]
            embeddings = embedding_model.embed_documents([item["embedding_input"] for item in batch])
            for item, vector in zip(batch, embeddings):
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
                        embedding=vector,
                        created_at=func.now(),
                    )
                )
            db.flush()
        db.commit()
    except Exception as exc:
        db.rollback()
        stats["failed_documents"] = stats["target_documents"]
        stats["embedded_documents"] = 0
        stats["created_chunks"] = 0
        stats["failures"].append({"error": str(exc)})

    return stats


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
        "failed_chunks": (
            db.query(func.count(PolicyChunk.id))
            .filter(PolicyChunk.embedding_status == "failed")
            .scalar()
            or 0
        ),
        "chunked_documents": db.query(func.count(func.distinct(PolicyChunk.document_id))).scalar() or 0,
    }


def chunk_to_source(chunk: PolicyChunk, similarity: float) -> Dict[str, Any]:
    metadata = chunk.chunk_metadata or {}
    return {
        "chunk_id": str(chunk.id),
        "policy_id": str(chunk.policy_id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "similarity": similarity,
        "chunk_text": chunk.chunk_text,
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


def rerank_sources_by_intent(
    sources: List[Dict[str, Any]],
    query_intent_tags: List[str],
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

        source["rerank_score"] = source["similarity"] + bonus
        reranked.append(source)

    return sorted(reranked, key=lambda item: item["rerank_score"], reverse=True)


@traceable_if_enabled("chat-rag-retrieve")
def retrieve_policy_chunk_sources(
    db: Session,
    query: str,
    *,
    limit: Optional[int] = None,
    embedding_model: Optional[EmbeddingModel] = None,
) -> Dict[str, Any]:
    model = embedding_model or create_embedding_model()
    expanded_query = build_query_embedding_text(query)
    intent_tags = infer_intent_tags(None, None, query)
    requested_limit = limit or settings.CHAT_RETRIEVAL_LIMIT
    results = search_policy_chunks(
        db=db,
        query=expanded_query,
        embedding_model=model,
        limit=max(requested_limit * 4, requested_limit),
    )
    sources = [chunk_to_source(chunk, similarity) for chunk, similarity in results]
    sources = rerank_sources_by_intent(sources, intent_tags)[:requested_limit]
    return {
        "query": query,
        "expanded_query": expanded_query,
        "intent_tags": intent_tags,
        "sources": sources,
    }


def build_context_text(sources: List[Dict[str, Any]]) -> str:
    blocks = []
    total_chars = 0
    for index, source in enumerate(sources, start=1):
        metadata = source.get("metadata") or {}
        block = (
            f"[근거 {index}]\n"
            f"정책명: {source.get('policy_title')}\n"
            f"문서유형: {source.get('document_type')}\n"
            f"문서제목: {source.get('document_title')}\n"
            f"신청기간: {source.get('apply_start')} ~ {source.get('apply_end')}\n"
            f"문의처: {', '.join(source.get('contact_points') or [])}\n"
            f"예상질문태그: {', '.join(metadata.get('intent_tags') or [])}\n"
            f"내용: {source.get('chunk_text')}\n"
        )
        if total_chars + len(block) > settings.CHAT_MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total_chars += len(block)
    return "\n".join(blocks)


def build_retrieval_only_answer(query: str, sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "관련 정책 문서 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요."

    lines = [
        "LLM 답변 생성이 비활성화되어 검색 근거를 먼저 정리합니다.",
        f"질문: {query}",
        "",
        "관련 근거:",
    ]
    for index, source in enumerate(sources[:3], start=1):
        lines.append(
            f"{index}. {source.get('policy_title') or '정책명 없음'} "
            f"({source.get('document_type')}, 유사도 {source.get('similarity'):.3f})"
        )
        lines.append(f"   - {source.get('chunk_text')}")
    return "\n".join(lines)


@traceable_if_enabled("chat-rag-answer")
def generate_chat_answer(query: str, sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "관련 정책 문서 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요."

    if settings.CHAT_COMPLETION_PROVIDER.lower() == "disabled":
        return build_retrieval_only_answer(query, sources)

    if settings.CHAT_COMPLETION_PROVIDER.lower() != "openai":
        return build_retrieval_only_answer(query, sources)

    try:
        from openai import OpenAI

        client = OpenAI()
        if is_langsmith_enabled():
            try:
                from langsmith import wrappers

                configure_langsmith_env()
                client = wrappers.wrap_openai(client)
            except ImportError:
                pass

        context_text = build_context_text(sources)
        response = client.chat.completions.create(
            model=settings.CHAT_COMPLETION_MODEL,
            messages=[
                {"role": "system", "content": settings.CHAT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"사용자 질문:\n{query}\n\n"
                        f"검색 근거:\n{context_text}\n\n"
                        "위 근거만 사용해서 답변해줘. "
                        "가능하면 신청 대상/방법/기간/서류/문의처를 항목별로 정리해줘."
                    ),
                },
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
    except Exception:
        return build_retrieval_only_answer(query, sources)


def answer_policy_question(db: Session, query: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
    retrieval = retrieve_policy_chunk_sources(db=db, query=query, limit=limit)
    answer = generate_chat_answer(query, retrieval["sources"])
    return {
        **retrieval,
        "answer": answer,
        "langsmith_enabled": is_langsmith_enabled(),
        "langsmith_project": settings.LANGSMITH_PROJECT if is_langsmith_enabled() else None,
    }
