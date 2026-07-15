from types import SimpleNamespace

from app.core.rag_utils import SimpleTextSplitter
from app.services.chat_rag import (
    _policy_chunks_are_current,
    build_chunk_embedding_input,
    build_embedding_context,
)


def test_short_duplicate_tail_is_removed():
    splitter = SimpleTextSplitter(
        chunk_size=100,
        chunk_overlap=20,
        min_chunk_size=20,
    )

    chunks = splitter._coalesce_short_tail(["지원 대상과 신청 방법 상시신청", "상시신청"])

    assert chunks == ["지원 대상과 신청 방법 상시신청"]


def test_short_unique_tail_is_merged_when_it_fits():
    splitter = SimpleTextSplitter(
        chunk_size=100,
        chunk_overlap=20,
        min_chunk_size=20,
    )

    chunks = splitter._coalesce_short_tail(["지원 대상과 신청 방법", "상시신청"])

    assert chunks == ["지원 대상과 신청 방법 상시신청"]


def test_embedding_input_keeps_section_context_separate():
    context = build_embedding_context(
        {
            "policy_title": "소상공인 지원사업",
            "document_type": "deadline",
            "document_title": "신청 기한",
            "section_title": "신청 기한",
        }
    )
    embedding_input = build_chunk_embedding_input(context, "상시신청")

    assert "섹션: 신청 기한" in embedding_input
    assert "청크 본문:\n상시신청" in embedding_input


def test_policy_chunk_incremental_check_skips_only_exact_embedding_input():
    prepared = {
        "chunk_index": 0,
        "chunk_hash": "chunk-hash",
        "embedding_source_hash": "source-hash",
    }
    existing = SimpleNamespace(
        chunk_index=0,
        chunk_hash="chunk-hash",
        chunk_metadata={"embedding_source_hash": "source-hash"},
        embedding_status="success",
        embedding_openai=[0.1],
        embedding_ollama=[0.2],
        embedding_openai_model="text-embedding-3-small",
        embedding_ollama_model="bge-m3",
    )

    assert _policy_chunks_are_current(
        [existing],
        [prepared],
        cloud_model_name="text-embedding-3-small",
        local_model_name="bge-m3",
    )

    existing.chunk_metadata = {"embedding_source_hash": "old-source-hash"}
    assert not _policy_chunks_are_current(
        [existing],
        [prepared],
        cloud_model_name="text-embedding-3-small",
        local_model_name="bge-m3",
    )


def test_policy_chunk_incremental_check_accepts_legacy_metadata_without_api_reembed():
    prepared = {
        "chunk_index": 0,
        "chunk_hash": "chunk-hash",
        "chunk_text": "지원 대상은 소상공인입니다.",
        "embedding_source_hash": "new-source-hash",
        "metadata": {
            "document_type": "eligibility",
            "embedding_source_hash": "new-source-hash",
        },
    }
    existing = SimpleNamespace(
        chunk_index=0,
        chunk_hash="chunk-hash",
        chunk_text="지원 대상은 소상공인입니다.",
        chunk_metadata={"document_type": "eligibility"},
        embedding_status="success",
        embedding_openai=[0.1],
        embedding_ollama=[0.2],
        embedding_openai_model="text-embedding-3-small",
        embedding_ollama_model="bge-m3",
    )

    assert _policy_chunks_are_current(
        [existing],
        [prepared],
        cloud_model_name="text-embedding-3-small",
        local_model_name="bge-m3",
    )
