from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import build_prep_vectors_once as prep_job
from app.models.prep import PrepVector


class _Guide:
    name = "사업자등록증명"

    def to_text(self) -> str:
        return "사업자등록증명은 홈택스에서 발급합니다."


class _Embedder:
    def __init__(self, dimension: int):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dimension for _text in texts]


class _Query:
    def __init__(self, db):
        self.db = db

    def all(self):
        return list(self.db.existing_rows)


class _Db:
    def __init__(self, existing_rows=None):
        self.rows = []
        self.existing_rows = list(existing_rows or [])
        self.deleted_rows = []
        self.committed = False
        self.closed = False

    def query(self, _model):
        return _Query(self)

    def add(self, row) -> None:
        self.rows.append(row)

    def delete(self, row) -> None:
        self.deleted_rows.append(row)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def test_build_prep_vectors_writes_openai_and_ollama_columns():
    db = _Db()
    cloud = _Embedder(1536)
    local = _Embedder(1024)

    with (
        patch.object(prep_job, "SessionLocal", return_value=db),
        patch.object(prep_job, "GUIDES", [_Guide()]),
        patch.object(prep_job, "get_embedding_model", side_effect=[cloud, local]),
        patch.object(
            prep_job,
            "resolve_embedding_model_spec_for_mode",
            side_effect=[
                SimpleNamespace(model="text-embedding-3-small"),
                SimpleNamespace(model="bge-m3"),
            ],
        ),
    ):
        stats = prep_job.build_prep_vectors_once()

    assert stats["written"] == 1
    assert stats["created"] == 1
    assert stats["skipped"] == 0
    assert db.deleted_rows == []
    assert db.committed is True
    assert db.closed is True
    assert len(db.rows) == 1
    row = db.rows[0]
    assert len(row.embedding_openai) == 1536
    assert len(row.embedding_ollama) == 1024
    assert row.embedding_openai_model == "text-embedding-3-small"
    assert row.embedding_ollama_model == "bge-m3"


def test_build_prep_vectors_skips_unchanged_guide_without_embedding_calls():
    text = _Guide().to_text()
    existing = PrepVector(
        document_name=_Guide.name,
        guide_text=text,
        embedding_openai=[0.1] * 1536,
        embedding_ollama=[0.1] * 1024,
        embedding_openai_model="text-embedding-3-small",
        embedding_ollama_model="bge-m3",
    )
    db = _Db([existing])

    with (
        patch.object(prep_job, "SessionLocal", return_value=db),
        patch.object(prep_job, "GUIDES", [_Guide()]),
        patch.object(prep_job, "get_embedding_model") as get_embedding_model,
        patch.object(
            prep_job,
            "resolve_embedding_model_spec_for_mode",
            side_effect=[
                SimpleNamespace(model="text-embedding-3-small"),
                SimpleNamespace(model="bge-m3"),
            ],
        ),
    ):
        stats = prep_job.build_prep_vectors_once()

    assert stats["written"] == 0
    assert stats["skipped"] == 1
    assert stats["created"] == 0
    assert stats["updated"] == 0
    get_embedding_model.assert_not_called()
