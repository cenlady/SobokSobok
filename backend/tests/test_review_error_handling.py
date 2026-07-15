from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.review import _mark_failed
from app.core.model_errors import ModelTimeoutError


class FakeReviewDb:
    def __init__(self, session):
        self.session = session
        self.committed = False
        self.rolled_back = False

    def get(self, _model, _session_id):
        return self.session

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_review_failure_stores_safe_error_code_without_upstream_detail():
    session = SimpleNamespace(review_status="diagnosing", summary=None, error_code=None)
    db = FakeReviewDb(session)

    _mark_failed(
        db,
        uuid4(),
        ModelTimeoutError("private document or upstream detail", feature="document_review"),
    )

    assert db.committed is True
    assert session.review_status == "failed"
    assert session.error_code == "LLM_TIMEOUT"
    assert "private document or upstream detail" not in session.summary
    assert "초과" in session.summary
