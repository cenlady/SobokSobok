from types import SimpleNamespace

from app.services.build_review_vectors import _review_vector_needs_refresh


def test_review_vector_refreshes_only_when_source_or_embedding_contract_changes():
    candidate = {"source_text": "사업자등록증 제출"}
    row = SimpleNamespace(
        source_text="사업자등록증 제출",
        embedding_openai=[0.1],
        embedding_ollama=[0.2],
        embedding_openai_model="text-embedding-3-small",
        embedding_ollama_model="bge-m3",
    )

    assert not _review_vector_needs_refresh(
        row,
        candidate,
        cloud_model_name="text-embedding-3-small",
        local_model_name="bge-m3",
    )

    candidate["source_text"] = "사업자등록증명 제출"
    assert _review_vector_needs_refresh(
        row,
        candidate,
        cloud_model_name="text-embedding-3-small",
        local_model_name="bge-m3",
    )
