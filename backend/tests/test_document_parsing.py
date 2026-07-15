import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.extract_attachments import (
    _is_unsupported_name,
    _run_kordoc,
)
from app.services.review_documents import _call_review_generate


@pytest.mark.parametrize("file_name", ["신청서.pdf", "사업계획서.docx"])
def test_pdf_and_docx_use_local_kordoc_parser(file_name: str) -> None:
    payload = {
        "success": True,
        "fileType": file_name.rsplit(".", 1)[-1],
        "markdown": "# 추출 본문\n내용",
    }
    completed = SimpleNamespace(stdout=json.dumps(payload).encode("utf-8"))

    assert not _is_unsupported_name(file_name, None)
    with patch("app.services.extract_attachments.subprocess.run", return_value=completed) as run:
        extracted = _run_kordoc(f"/private/{file_name}")

    assert extracted == payload["markdown"]
    command = run.call_args.args[0]
    assert command[:4] == [settings.KORDOC_CMD, "--silent", "--format", "json"]


def test_review_text_uses_the_profile_selected_model_mode() -> None:
    with patch("app.services.review_documents.get_chat_model") as get_model:
        get_model.return_value.generate.return_value = "{}"
        _call_review_generate("파싱 원문", model_mode="cloud")

    get_model.assert_called_once_with("document_review", model_mode="cloud")


def test_pptx_remains_unsupported_by_local_parser() -> None:
    assert _is_unsupported_name("발표자료.pptx", None)
