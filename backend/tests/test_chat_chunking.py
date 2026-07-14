from app.core.rag_utils import SimpleTextSplitter
from app.services.chat_rag import build_chunk_embedding_input, build_embedding_context


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
