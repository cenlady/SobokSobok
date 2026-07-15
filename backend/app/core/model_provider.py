from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from collections.abc import Iterator
from typing import Any

import httpx

from app.core.config import settings
from app.core.model_errors import (
    ModelConfigurationError,
    ModelResponseError,
    classify_model_exception,
)
from app.core.model_logging import log_model_call


SUPPORTED_PROVIDERS = {"openai", "ollama", "gemini"}
EXTERNAL_PROVIDERS = {"openai", "gemini"}
SUPPORTED_MODEL_MODES = {"cloud", "local"}


@dataclass(frozen=True)
class ModelSpec:
    feature: str
    task: str
    provider: str
    model: str
    allow_external: bool
    dimensions: int | None = None


_FEATURE_ALIASES = {
    "recommend": "recommendation",
    "policy_recommendation": "recommendation",
    "review": "document_review",
    "documents": "document_review",
    "prep_guides": "prep",
    "calendar": "calendar_coach",
    "normalize": "normalization",
}


def _feature_name(feature: str) -> str:
    normalized = feature.strip().lower()
    return _FEATURE_ALIASES.get(normalized, normalized)


def _provider_value(value: str, default: str) -> str:
    return (value.strip() or default.strip()).lower()


def _default_model(provider: str, task: str) -> str:
    if task == "embedding":
        return {
            "openai": settings.OPENAI_EMBEDDING_MODEL,
            "ollama": settings.OLLAMA_EMBEDDING_MODEL,
            "gemini": settings.GEMINI_EMBEDDING_MODEL,
        }.get(provider, "")
    return {
        "openai": settings.OPENAI_CHAT_MODEL,
        "ollama": settings.OLLAMA_CHAT_MODEL,
        "gemini": settings.GEMINI_TEXT_MODEL,
    }.get(provider, "")


def normalize_model_mode(model_mode: str | None) -> str | None:
    if model_mode is None:
        return None
    normalized = model_mode.strip().lower()
    if normalized not in SUPPORTED_MODEL_MODES:
        raise ModelConfigurationError(
            f"지원하지 않는 사용자 AI 모드입니다: {model_mode}. 허용값: cloud, local"
        )
    return normalized


_USER_MODE_FIELDS = {
    "chat": ("chat_model_mode", "cloud"),
    "recommendation": ("recommend_model_mode", "cloud"),
    "policy_summary": ("policy_summary_model_mode", "cloud"),
    "calendar_coach": ("calendar_coach_model_mode", "cloud"),
    "document_review": ("document_review_model_mode", "local"),
}


def get_user_model_mode(user: Any, feature: str | None = None) -> str:
    """사용자 프로필의 기능별 cloud/local 선택을 읽는다.

    feature를 생략한 구 호출부는 레거시 ai_model_mode를 사용한다. 신규 호출부는 반드시
    기능명을 넘겨 기능별 선택과 서로 다른 기본값을 적용한다.
    """
    profile = getattr(user, "profile", None)
    if feature is None:
        return normalize_model_mode(getattr(profile, "ai_model_mode", None)) or "cloud"
    normalized_feature = _feature_name(feature)
    field_name, default_mode = _USER_MODE_FIELDS.get(
        normalized_feature,
        ("ai_model_mode", "cloud"),
    )
    return normalize_model_mode(getattr(profile, field_name, None)) or default_mode


def _spec_for_model_mode(spec: ModelSpec, model_mode: str | None) -> ModelSpec:
    normalized = normalize_model_mode(model_mode)
    if normalized is None:
        return spec
    provider = "openai" if normalized == "cloud" else "ollama"
    dimensions = spec.dimensions
    model = _default_model(provider, spec.task)
    if spec.task == "chat":
        feature_models = {
            "chat": (settings.CHAT_CLOUD_LLM_MODEL, settings.CHAT_LOCAL_LLM_MODEL),
            "recommendation": (
                settings.RECOMMEND_CLOUD_LLM_MODEL,
                settings.RECOMMEND_LOCAL_LLM_MODEL,
            ),
            "policy_summary": (
                settings.POLICY_SUMMARY_CLOUD_LLM_MODEL,
                settings.POLICY_SUMMARY_LOCAL_LLM_MODEL,
            ),
            "calendar_coach": (
                settings.CALENDAR_COACH_CLOUD_LLM_MODEL,
                settings.CALENDAR_COACH_LOCAL_LLM_MODEL,
            ),
            "document_review": (
                settings.DOCUMENT_REVIEW_CLOUD_LLM_MODEL,
                settings.DOCUMENT_REVIEW_LOCAL_LLM_MODEL,
            ),
        }
        if spec.feature in feature_models:
            model = feature_models[spec.feature][0 if normalized == "cloud" else 1]
    else:
        feature_embeddings = {
            "chat": (
                settings.CHAT_CLOUD_EMBEDDING_MODEL,
                settings.CHAT_CLOUD_EMBEDDING_DIMENSIONS,
                settings.CHAT_LOCAL_EMBEDDING_MODEL,
                settings.CHAT_LOCAL_EMBEDDING_DIMENSIONS,
            ),
            "recommendation": (
                settings.RECOMMEND_CLOUD_EMBEDDING_MODEL,
                settings.RECOMMEND_CLOUD_EMBEDDING_DIMENSIONS,
                settings.RECOMMEND_LOCAL_EMBEDDING_MODEL,
                settings.RECOMMEND_LOCAL_EMBEDDING_DIMENSIONS,
            ),
            "document_review": (
                settings.DOCUMENT_REVIEW_CLOUD_EMBEDDING_MODEL,
                settings.DOCUMENT_REVIEW_CLOUD_EMBEDDING_DIMENSIONS,
                settings.DOCUMENT_REVIEW_LOCAL_EMBEDDING_MODEL,
                settings.DOCUMENT_REVIEW_LOCAL_EMBEDDING_DIMENSIONS,
            ),
            "prep": (
                settings.PREP_CLOUD_EMBEDDING_MODEL,
                settings.PREP_CLOUD_EMBEDDING_DIMENSIONS,
                settings.PREP_LOCAL_EMBEDDING_MODEL,
                settings.PREP_LOCAL_EMBEDDING_DIMENSIONS,
            ),
        }
        if spec.feature in feature_embeddings:
            cloud_model, cloud_dim, local_model, local_dim = feature_embeddings[spec.feature]
            if normalized == "cloud":
                model, dimensions = cloud_model, cloud_dim
            else:
                model, dimensions = local_model, local_dim
        else:
            dimensions = (
                settings.OPENAI_EMBEDDING_DIMENSIONS
                if normalized == "cloud"
                else settings.OLLAMA_EMBEDDING_DIMENSIONS
            )
    return _validate_spec(
        replace(
            spec,
            provider=provider,
            model=model,
            dimensions=dimensions,
        )
    )


def _validate_spec(spec: ModelSpec) -> ModelSpec:
    if spec.provider not in SUPPORTED_PROVIDERS:
        raise ModelConfigurationError(
            f"{spec.feature}의 {spec.task} provider '{spec.provider}'는 지원하지 않습니다. "
            f"허용값: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )
    if not spec.model.strip():
        raise ModelConfigurationError(f"{spec.feature}의 {spec.task} model이 비어 있습니다.")
    if spec.provider in EXTERNAL_PROVIDERS and not spec.allow_external:
        raise ModelConfigurationError(
            f"{spec.feature}는 외부 모델 전송이 금지되어 있어 {spec.provider}를 사용할 수 없습니다."
        )
    if spec.task == "embedding" and (spec.dimensions is None or spec.dimensions <= 0):
        raise ModelConfigurationError(f"{spec.feature}의 embedding dimensions는 양수여야 합니다.")
    return spec


def resolve_chat_model_spec(feature: str) -> ModelSpec:
    feature = _feature_name(feature)
    values = {
        "chat": (
            settings.CHAT_LLM_PROVIDER,
            settings.CHAT_LLM_MODEL,
            settings.CHAT_ALLOW_EXTERNAL,
        ),
        "recommendation": (
            settings.RECOMMEND_LLM_PROVIDER,
            settings.RECOMMEND_LLM_MODEL,
            settings.RECOMMEND_ALLOW_EXTERNAL,
        ),
        "policy_summary": (
            settings.POLICY_SUMMARY_LLM_PROVIDER,
            settings.POLICY_SUMMARY_LLM_MODEL,
            settings.POLICY_SUMMARY_ALLOW_EXTERNAL,
        ),
        "normalization": (
            settings.NORMALIZATION_LLM_PROVIDER,
            settings.NORMALIZATION_LLM_MODEL,
            settings.NORMALIZATION_ALLOW_EXTERNAL,
        ),
        "document_review": (
            settings.DOCUMENT_REVIEW_LLM_PROVIDER,
            settings.DOCUMENT_REVIEW_LLM_MODEL,
            True,
        ),
        "calendar_coach": (
            settings.CALENDAR_COACH_LLM_PROVIDER,
            settings.CALENDAR_COACH_LLM_MODEL,
            settings.CALENDAR_COACH_ALLOW_EXTERNAL,
        ),
    }
    if feature not in values:
        raise ModelConfigurationError(f"알 수 없는 LLM 기능입니다: {feature}")
    provider, model, allow_external = values[feature]
    provider = _provider_value(provider, settings.DEFAULT_LLM_PROVIDER)
    model = model.strip() or _default_model(provider, "chat")
    return _validate_spec(
        ModelSpec(
            feature=feature,
            task="chat",
            provider=provider,
            model=model,
            allow_external=allow_external,
        )
    )


def resolve_embedding_model_spec(feature: str) -> ModelSpec:
    feature = _feature_name(feature)
    values = {
        "chat": (
            settings.CHAT_EMBEDDING_PROVIDER,
            settings.CHAT_EMBEDDING_MODEL,
            settings.CHAT_EMBEDDING_DIMENSIONS,
            settings.CHAT_ALLOW_EXTERNAL,
        ),
        "recommendation": (
            settings.RECOMMEND_EMBEDDING_PROVIDER,
            settings.RECOMMEND_EMBEDDING_MODEL,
            settings.RECOMMEND_EMBEDDING_DIMENSIONS,
            settings.RECOMMEND_ALLOW_EXTERNAL,
        ),
        "document_review": (
            settings.DOCUMENT_REVIEW_EMBEDDING_PROVIDER,
            settings.DOCUMENT_REVIEW_EMBEDDING_MODEL,
            settings.DOCUMENT_REVIEW_EMBEDDING_DIMENSIONS,
            True,
        ),
        "prep": (
            settings.PREP_EMBEDDING_PROVIDER,
            settings.PREP_EMBEDDING_MODEL,
            settings.PREP_EMBEDDING_DIMENSIONS,
            settings.PREP_ALLOW_EXTERNAL,
        ),
    }
    if feature not in values:
        raise ModelConfigurationError(f"알 수 없는 임베딩 기능입니다: {feature}")
    provider, model, dimensions, allow_external = values[feature]
    provider = _provider_value(provider, settings.DEFAULT_EMBEDDING_PROVIDER)
    model = model.strip() or _default_model(provider, "embedding")
    return _validate_spec(
        ModelSpec(
            feature=feature,
            task="embedding",
            provider=provider,
            model=model,
            dimensions=dimensions,
            allow_external=allow_external,
        )
    )


def resolve_chat_model_spec_for_mode(feature: str, model_mode: str | None) -> ModelSpec:
    return _spec_for_model_mode(resolve_chat_model_spec(feature), model_mode)


def resolve_embedding_model_spec_for_mode(feature: str, model_mode: str | None) -> ModelSpec:
    return _spec_for_model_mode(resolve_embedding_model_spec(feature), model_mode)


class ChatModel:
    def __init__(self, spec: ModelSpec):
        self.spec = spec

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        stage: str,
        source_module: str,
        source_function: str,
        temperature: float = 0.2,
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        started = time.perf_counter()
        output = ""
        try:
            output = self._generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                response_schema=response_schema,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            ).strip()
            log_model_call(
                feature=self.spec.feature,
                task="chat",
                stage=stage,
                provider=self.spec.provider,
                model=self.spec.model,
                source_module=source_module,
                source_function=source_function,
                status="success",
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_chars=len(system_prompt) + len(user_prompt),
                output_chars=len(output),
                result_count=1 if output else 0,
            )
            return output
        except Exception as exc:
            log_model_call(
                feature=self.spec.feature,
                task="chat",
                stage=stage,
                provider=self.spec.provider,
                model=self.spec.model,
                source_module=source_module,
                source_function=source_function,
                status="error",
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_chars=len(system_prompt) + len(user_prompt),
                output_chars=len(output),
                error_type=type(exc).__name__,
            )
            raise classify_model_exception(
                exc,
                feature=self.spec.feature,
                task="chat",
                provider=self.spec.provider,
                model=self.spec.model,
            ) from exc

    def _generate(self, **kwargs: Any) -> str:
        raise NotImplementedError

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        stage: str,
        source_module: str,
        source_function: str,
        temperature: float = 0.2,
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[str]:
        started = time.perf_counter()
        output_chars = 0
        try:
            for chunk in self._stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                response_schema=response_schema,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            ):
                if not chunk:
                    continue
                output_chars += len(chunk)
                yield chunk

            log_model_call(
                feature=self.spec.feature,
                task="chat",
                stage=stage,
                provider=self.spec.provider,
                model=self.spec.model,
                source_module=source_module,
                source_function=source_function,
                status="success",
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_chars=len(system_prompt) + len(user_prompt),
                output_chars=output_chars,
                result_count=1 if output_chars else 0,
            )
        except Exception as exc:
            log_model_call(
                feature=self.spec.feature,
                task="chat",
                stage=stage,
                provider=self.spec.provider,
                model=self.spec.model,
                source_module=source_module,
                source_function=source_function,
                status="error",
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_chars=len(system_prompt) + len(user_prompt),
                output_chars=output_chars,
                error_type=type(exc).__name__,
            )
            raise classify_model_exception(
                exc,
                feature=self.spec.feature,
                task="chat",
                provider=self.spec.provider,
                model=self.spec.model,
            ) from exc

    def _stream(self, **kwargs: Any) -> Iterator[str]:
        raise NotImplementedError


class OpenAIChatModel(ChatModel):
    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        if not settings.OPENAI_API_KEY:
            raise ModelConfigurationError(
                "OPENAI_API_KEY가 설정되지 않았습니다.",
                feature=spec.feature,
                task="chat",
                provider=spec.provider,
                model=spec.model,
            )
        from openai import OpenAI

        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

    def _generate(self, **kwargs: Any) -> str:
        response_schema = kwargs["response_schema"]
        request: dict[str, Any] = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": kwargs["system_prompt"]},
                {"role": "user", "content": kwargs["user_prompt"]},
            ],
            "temperature": kwargs["temperature"],
        }
        if kwargs["max_output_tokens"] is not None:
            request["max_tokens"] = kwargs["max_output_tokens"]
        if response_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "soboksobok_response",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        timeout = kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS
        response = self.client.with_options(timeout=timeout).chat.completions.create(**request)
        return response.choices[0].message.content or ""

    def _stream(self, **kwargs: Any) -> Iterator[str]:
        response_schema = kwargs["response_schema"]
        request: dict[str, Any] = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": kwargs["system_prompt"]},
                {"role": "user", "content": kwargs["user_prompt"]},
            ],
            "temperature": kwargs["temperature"],
            "stream": True,
        }
        if kwargs["max_output_tokens"] is not None:
            request["max_tokens"] = kwargs["max_output_tokens"]
        if response_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "soboksobok_response",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        timeout = kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS
        response = self.client.with_options(timeout=timeout).chat.completions.create(**request)
        for chunk in response:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content


class GeminiChatModel(ChatModel):
    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        if not settings.GEMINI_API_KEY:
            raise ModelConfigurationError(
                "GEMINI_API_KEY가 설정되지 않았습니다.",
                feature=spec.feature,
                task="chat",
                provider=spec.provider,
                model=spec.model,
            )

    def _generate(self, **kwargs: Any) -> str:
        from google import genai
        from google.genai import types

        config_args: dict[str, Any] = {"temperature": kwargs["temperature"]}
        if kwargs["response_schema"] is not None:
            config_args.update(
                response_mime_type="application/json",
                response_json_schema=kwargs["response_schema"],
            )
        if kwargs["max_output_tokens"] is not None:
            config_args["max_output_tokens"] = kwargs["max_output_tokens"]
        timeout_seconds = kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        try:
            response = client.models.generate_content(
                model=self.spec.model,
                contents=f"{kwargs['system_prompt']}\n\n{kwargs['user_prompt']}",
                config=types.GenerateContentConfig(**config_args),
            )
            return response.text or ""
        finally:
            client.close()

    def _stream(self, **kwargs: Any) -> Iterator[str]:
        from google import genai
        from google.genai import types

        config_args: dict[str, Any] = {"temperature": kwargs["temperature"]}
        if kwargs["response_schema"] is not None:
            config_args.update(
                response_mime_type="application/json",
                response_json_schema=kwargs["response_schema"],
            )
        if kwargs["max_output_tokens"] is not None:
            config_args["max_output_tokens"] = kwargs["max_output_tokens"]
        timeout_seconds = kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        try:
            chunks = client.models.generate_content_stream(
                model=self.spec.model,
                contents=f"{kwargs['system_prompt']}\n\n{kwargs['user_prompt']}",
                config=types.GenerateContentConfig(**config_args),
            )
            for chunk in chunks:
                content = getattr(chunk, "text", None)
                if content:
                    yield content
        finally:
            client.close()


class OllamaChatModel(ChatModel):
    def _generate(self, **kwargs: Any) -> str:
        payload: dict[str, Any] = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": kwargs["system_prompt"]},
                {"role": "user", "content": kwargs["user_prompt"]},
            ],
            "stream": False,
            "options": {"temperature": kwargs["temperature"]},
        }
        if kwargs["response_schema"] is not None:
            payload["format"] = kwargs["response_schema"]
        response = httpx.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json=payload,
            timeout=kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")

    def _stream(self, **kwargs: Any) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": kwargs["system_prompt"]},
                {"role": "user", "content": kwargs["user_prompt"]},
            ],
            "stream": True,
            "options": {"temperature": kwargs["temperature"]},
        }
        if kwargs["response_schema"] is not None:
            payload["format"] = kwargs["response_schema"]
        with httpx.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json=payload,
            timeout=kwargs["timeout_seconds"] or settings.LLM_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content


def get_chat_model(
    feature: str,
    provider: str | None = None,
    model_name: str | None = None,
    model_mode: str | None = None,
) -> ChatModel:
    spec = resolve_chat_model_spec_for_mode(feature, model_mode)
    if provider is not None or model_name is not None:
        spec = _validate_spec(
            replace(
                spec,
                provider=(provider or spec.provider).strip().lower(),
                model=(model_name or spec.model).strip(),
            )
        )
    if spec.provider == "openai":
        return OpenAIChatModel(spec)
    if spec.provider == "gemini":
        return GeminiChatModel(spec)
    return OllamaChatModel(spec)


def get_embedding_model(
    feature: str,
    provider: str | None = None,
    model_name: str | None = None,
    model_mode: str | None = None,
):
    spec = resolve_embedding_model_spec_for_mode(feature, model_mode)
    if provider is not None or model_name is not None:
        spec = _validate_spec(
            replace(
                spec,
                provider=(provider or spec.provider).strip().lower(),
                model=(model_name or spec.model).strip(),
            )
        )
    # 순환 import를 피하기 위해 생성 시점에만 구현체를 가져온다.
    from app.core.rag_utils import (
        GeminiEmbeddingModel,
        OllamaEmbeddingModel,
        OpenAIEmbeddingModel,
    )

    common = {
        "model_name": spec.model,
        "expected_dimensions": spec.dimensions,
        "feature": spec.feature,
    }
    if spec.provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ModelConfigurationError(
                "OPENAI_API_KEY가 설정되지 않았습니다.",
                feature=spec.feature,
                task="embedding",
                provider=spec.provider,
                model=spec.model,
            )
        return OpenAIEmbeddingModel(
            api_key=settings.OPENAI_API_KEY,
            timeout_seconds=settings.LLM_EMBEDDING_TIMEOUT_SECONDS,
            **common,
        )
    if spec.provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ModelConfigurationError(
                "GEMINI_API_KEY가 설정되지 않았습니다.",
                feature=spec.feature,
                task="embedding",
                provider=spec.provider,
                model=spec.model,
            )
        return GeminiEmbeddingModel(
            api_key=settings.GEMINI_API_KEY,
            timeout_seconds=settings.LLM_EMBEDDING_TIMEOUT_SECONDS,
            **common,
        )
    return OllamaEmbeddingModel(
        base_url=settings.OLLAMA_BASE_URL,
        timeout_seconds=settings.LLM_EMBEDDING_TIMEOUT_SECONDS,
        **common,
    )


def validate_model_settings() -> None:
    """앱 시작/관리 명령에서 사용할 수 있는 기능별 설정 검증 함수."""
    if settings.LLM_LOG_CONTENT or settings.LLM_LOG_PREVIEW_CHARS > 0:
        raise ModelConfigurationError(
            "개인정보 보호를 위해 LLM_LOG_CONTENT=false, LLM_LOG_PREVIEW_CHARS=0이어야 합니다."
        )
    for feature in (
        "chat",
        "recommendation",
        "policy_summary",
        "normalization",
        "document_review",
        "calendar_coach",
    ):
        resolve_chat_model_spec(feature)
    for feature in ("chat", "recommendation", "document_review", "prep"):
        resolve_embedding_model_spec(feature)
    # 사용자 프로필 전환 경로는 두 공급자 설정이 모두 유효해야 한다.
    for feature in (
        "chat",
        "recommendation",
        "policy_summary",
        "calendar_coach",
        "document_review",
    ):
        resolve_chat_model_spec_for_mode(feature, "cloud")
        resolve_chat_model_spec_for_mode(feature, "local")
    for feature in ("chat", "recommendation", "document_review", "prep"):
        resolve_embedding_model_spec_for_mode(feature, "cloud")
        resolve_embedding_model_spec_for_mode(feature, "local")


def parse_json_response(text: str) -> Any:
    """공급자별 마크다운 감싸기를 제거하고 JSON을 파싱한다."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        raise ModelResponseError("모델이 유효한 JSON을 반환하지 않았습니다.") from exc
