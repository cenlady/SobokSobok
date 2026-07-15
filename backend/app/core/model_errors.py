from __future__ import annotations

import json

import httpx


class ModelServiceError(RuntimeError):
    """외부/로컬 모델 호출 실패의 안전한 공통 예외."""

    code = "LLM_UPSTREAM_ERROR"
    status_code = 502
    default_public_message = "AI 서비스 요청에 실패했습니다. 잠시 후 다시 시도해주세요."

    def __init__(
        self,
        message: str | None = None,
        *,
        feature: str | None = None,
        task: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(message or self.default_public_message)
        self.feature = feature
        self.task = task
        self.provider = provider
        self.model = model
        self.public_message = self.default_public_message


class ModelTimeoutError(ModelServiceError):
    code = "LLM_TIMEOUT"
    status_code = 504
    default_public_message = "AI 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."


class ModelConnectionError(ModelServiceError):
    code = "LLM_CONNECTION_ERROR"
    status_code = 502
    default_public_message = "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해주세요."


class ModelConfigurationError(ModelServiceError):
    code = "LLM_CONFIGURATION_ERROR"
    status_code = 503
    default_public_message = "AI 모델 설정에 문제가 있습니다. 관리자에게 문의해주세요."


class ModelResponseError(ModelServiceError):
    code = "LLM_INVALID_RESPONSE"
    status_code = 502
    default_public_message = "AI 응답을 처리하지 못했습니다. 잠시 후 다시 시도해주세요."


class ModelUpstreamError(ModelServiceError):
    pass


def classify_model_exception(
    exc: Exception,
    *,
    feature: str,
    task: str,
    provider: str,
    model: str,
) -> ModelServiceError:
    """SDK 종류와 무관하게 사용자에게 노출할 수 있는 모델 예외로 변환한다."""
    if isinstance(exc, ModelServiceError):
        return exc

    context = {
        "feature": feature,
        "task": task,
        "provider": provider,
        "model": model,
    }
    class_name = type(exc).__name__.lower()
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)

    if (
        isinstance(exc, (TimeoutError, httpx.TimeoutException))
        or "timeout" in class_name
        or "deadlineexceeded" in class_name
    ):
        return ModelTimeoutError(str(exc), **context)

    if (
        isinstance(exc, (ConnectionError, httpx.NetworkError))
        or "connection" in class_name
        or "connecterror" in class_name
    ):
        return ModelConnectionError(str(exc), **context)

    if (
        class_name in {"authenticationerror", "permissiondeniederror"}
        or status_code in {401, 403, 404}
    ):
        return ModelConfigurationError(str(exc), **context)

    if isinstance(exc, (json.JSONDecodeError, UnicodeError)):
        return ModelResponseError(str(exc), **context)

    return ModelUpstreamError(str(exc), **context)


def public_model_error(exc: Exception) -> tuple[str, str]:
    """백그라운드 작업에 저장할 안전한 (오류 코드, 안내 문구)."""
    if isinstance(exc, ModelServiceError):
        return exc.code, exc.public_message
    return ModelUpstreamError.code, ModelUpstreamError.default_public_message
