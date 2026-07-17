import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.model_errors import (
    ModelConfigurationError,
    ModelConnectionError,
    ModelTimeoutError,
)
from app.core.model_provider import (
    get_chat_model,
    get_embedding_model,
    get_user_model_mode,
    resolve_chat_model_spec,
    resolve_chat_model_spec_for_mode,
    resolve_embedding_model_spec,
    resolve_embedding_model_spec_for_mode,
)
from app.models.chat import PolicyChunk
from app.models.prep import PrepVector
from app.models.recommend import RecommendationVector
from app.models.review import ReviewVector
from app.schemas.user import ProfileUpsertRequest
from app.services.prep_rag import prep_vector_column_for_mode


class FakeOllamaResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": "응답 원문도 로그에 나오면 안 됩니다"}}


class ModelProviderTests(unittest.TestCase):
    def test_omitted_mode_uses_each_feature_default(self) -> None:
        self.assertEqual(resolve_chat_model_spec("chat").provider, "openai")
        self.assertEqual(resolve_chat_model_spec("recommendation").provider, "openai")
        self.assertEqual(resolve_chat_model_spec("document_review").provider, "ollama")
        self.assertEqual(resolve_embedding_model_spec("chat").provider, "openai")
        self.assertEqual(resolve_embedding_model_spec("recommendation").provider, "openai")
        self.assertEqual(resolve_embedding_model_spec("document_review").provider, "ollama")
        self.assertEqual(resolve_embedding_model_spec("prep").provider, "ollama")

    def test_user_cloud_and_local_modes_choose_expected_chat_provider(self) -> None:
        cloud = resolve_chat_model_spec_for_mode("chat", "cloud")
        local = resolve_chat_model_spec_for_mode("chat", "local")

        self.assertEqual((cloud.provider, cloud.model), ("openai", settings.CHAT_CLOUD_LLM_MODEL))
        self.assertEqual((local.provider, local.model), ("ollama", settings.CHAT_LOCAL_LLM_MODEL))

    def test_dual_embedding_modes_keep_dimensions_separate(self) -> None:
        cloud = resolve_embedding_model_spec_for_mode("recommendation", "cloud")
        local = resolve_embedding_model_spec_for_mode("recommendation", "local")

        self.assertEqual(cloud.provider, "openai")
        self.assertEqual(cloud.dimensions, 1536)
        self.assertEqual(local.provider, "ollama")
        self.assertEqual(local.dimensions, 1024)
        self.assertEqual(PolicyChunk.embedding_openai.type.dim, 1536)
        self.assertEqual(PolicyChunk.embedding_ollama.type.dim, 1024)
        self.assertEqual(RecommendationVector.embedding_openai.type.dim, 1536)
        self.assertEqual(RecommendationVector.embedding_ollama.type.dim, 1024)

    def test_prep_dual_embeddings_follow_cloud_and_local_modes(self) -> None:
        cloud = resolve_embedding_model_spec_for_mode("prep", "cloud")
        local = resolve_embedding_model_spec_for_mode("prep", "local")

        self.assertEqual((cloud.provider, cloud.dimensions), ("openai", 1536))
        self.assertEqual((local.provider, local.dimensions), ("ollama", 1024))
        self.assertEqual(PrepVector.embedding_openai.type.dim, 1536)
        self.assertEqual(PrepVector.embedding_ollama.type.dim, 1024)

        cloud_mode, cloud_column = prep_vector_column_for_mode("cloud")
        local_mode, local_column = prep_vector_column_for_mode("local")
        self.assertEqual(cloud_mode, "cloud")
        self.assertEqual(local_mode, "local")
        self.assertIs(cloud_column, PrepVector.embedding_openai)
        self.assertIs(local_column, PrepVector.embedding_ollama)

    def test_vector_models_do_not_expose_legacy_embedding_column(self) -> None:
        for model in (PolicyChunk, RecommendationVector, ReviewVector, PrepVector):
            self.assertFalse(hasattr(model, "embedding"), model.__name__)

    def test_document_review_cloud_and_local_modes_are_both_selectable(self) -> None:
        cloud_chat = resolve_chat_model_spec_for_mode("document_review", "cloud")
        local_chat = resolve_chat_model_spec_for_mode("document_review", "local")
        cloud_embedding = resolve_embedding_model_spec_for_mode("document_review", "cloud")
        local_embedding = resolve_embedding_model_spec_for_mode("document_review", "local")

        self.assertEqual(
            (cloud_chat.provider, cloud_chat.model),
            ("openai", settings.DOCUMENT_REVIEW_CLOUD_LLM_MODEL),
        )
        self.assertEqual((local_chat.provider, local_chat.model), ("ollama", "exaone3.5"))
        self.assertEqual((cloud_embedding.provider, cloud_embedding.dimensions), ("openai", 1536))
        self.assertEqual((local_embedding.provider, local_embedding.dimensions), ("ollama", 1024))
        self.assertEqual(ReviewVector.embedding_openai.type.dim, 1536)
        self.assertEqual(ReviewVector.embedding_ollama.type.dim, 1024)

    @patch("app.core.model_provider.httpx.post")
    def test_model_log_contains_metadata_but_not_prompt_or_response(self, mock_post) -> None:
        mock_post.return_value = FakeOllamaResponse()
        secret_prompt = "개인정보 010-1234-5678"

        with self.assertLogs("app.model_calls", level="INFO") as captured:
            result = get_chat_model("chat", model_mode="local").generate(
                system_prompt="안전 테스트",
                user_prompt=secret_prompt,
                stage="test",
                source_module=__name__,
                source_function="test_model_log_contains_metadata_but_not_prompt_or_response",
            )

        log_text = "\n".join(captured.output)
        self.assertIn("provider=ollama", log_text)
        self.assertIn("input_chars=", log_text)
        self.assertNotIn(secret_prompt, log_text)
        self.assertNotIn(result, log_text)

    def test_profile_feature_modes_keep_existing_defaults(self) -> None:
        payload = ProfileUpsertRequest()
        self.assertEqual(payload.chat_model_mode, "cloud")
        self.assertEqual(payload.recommend_model_mode, "cloud")
        self.assertEqual(payload.policy_summary_model_mode, "cloud")
        self.assertEqual(payload.calendar_coach_model_mode, "cloud")
        self.assertEqual(payload.document_review_model_mode, "local")

        user = SimpleNamespace(profile=SimpleNamespace(document_review_model_mode="cloud"))
        self.assertEqual(get_user_model_mode(user, "document_review"), "cloud")

        with self.assertRaises(ValidationError):
            ProfileUpsertRequest(document_review_model_mode="paid")

    @patch("app.core.model_provider.httpx.post")
    def test_ollama_timeout_is_classified(self, mock_post) -> None:
        mock_post.side_effect = httpx.ReadTimeout("private upstream detail")

        with self.assertRaises(ModelTimeoutError):
            get_chat_model("chat", model_mode="local").generate(
                system_prompt="system",
                user_prompt="user",
                stage="test_timeout",
                source_module=__name__,
                source_function="test_ollama_timeout_is_classified",
            )

    @patch("app.core.model_provider.httpx.post")
    def test_ollama_connection_failure_is_classified(self, mock_post) -> None:
        mock_post.side_effect = httpx.ConnectError(
            "private upstream detail",
            request=httpx.Request("POST", "http://ollama/api/chat"),
        )

        with self.assertRaises(ModelConnectionError):
            get_chat_model("chat", model_mode="local").generate(
                system_prompt="system",
                user_prompt="user",
                stage="test_connection",
                source_module=__name__,
                source_function="test_ollama_connection_failure_is_classified",
            )

    def test_missing_openai_key_is_configuration_error(self) -> None:
        with patch.object(settings, "OPENAI_API_KEY", ""):
            with self.assertRaises(ModelConfigurationError):
                get_chat_model("chat", model_mode="cloud")

    def test_embedding_timeout_is_classified(self) -> None:
        model = get_embedding_model("chat", model_mode="local")
        try:
            with patch.object(
                model.client,
                "post",
                side_effect=httpx.ReadTimeout("private embedding detail"),
            ):
                with self.assertRaises(ModelTimeoutError):
                    model.embed_text("민감할 수 있는 입력")
        finally:
            model.client.close()

    def test_fastapi_model_error_handler_returns_safe_status_and_body(self) -> None:
        from app.main import model_service_error_handler

        request = SimpleNamespace(url=SimpleNamespace(path="/api/v1/chat/ask"))
        response = asyncio.run(
            model_service_error_handler(
                request,
                ModelTimeoutError("private upstream detail", feature="chat"),
            )
        )

        self.assertEqual(response.status_code, 504)
        body = response.body.decode("utf-8")
        self.assertIn("LLM_TIMEOUT", body)
        self.assertNotIn("private upstream detail", body)


if __name__ == "__main__":
    unittest.main()
