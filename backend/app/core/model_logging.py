from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger("app.model_calls")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.propagate = False


def _safe(value: Any) -> str:
    """로그 한 줄을 깨지 않도록 메타데이터 값만 정규화한다."""
    if value is None:
        return "-"
    return str(value).replace("\n", " ").replace("\r", " ")[:120]


def log_model_call(
    *,
    feature: str,
    task: str,
    stage: str,
    provider: str,
    model: str,
    source_module: str,
    source_function: str,
    status: str,
    latency_ms: int,
    input_type: str = "text",
    input_count: int = 1,
    input_chars: int = 0,
    output_chars: int = 0,
    result_count: int = 0,
    embedding_dimensions: int | None = None,
    retry_count: int = 0,
    error_type: str | None = None,
) -> None:
    """모델 호출 메타데이터만 한 줄로 기록한다.

    프롬프트, 응답, 벡터, 파일명, API 키와 토큰은 인자로 받지 않으므로
    개인정보가 실수로 로그에 섞이지 않는다.
    """
    if not settings.LLM_CALL_LOGGING_ENABLED:
        return

    level = getattr(logging, settings.LLM_LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    logger.log(
        level,
        "model_call "
        f"service={_safe(settings.SERVICE_NAME)} "
        f"feature={_safe(feature)} task={_safe(task)} stage={_safe(stage)} "
        f"provider={_safe(provider)} model={_safe(model)} "
        f"source={_safe(source_module)}:{_safe(source_function)} "
        f"input_type={_safe(input_type)} input_count={input_count} "
        f"input_chars={input_chars} output_chars={output_chars} "
        f"result_count={result_count} dimensions={_safe(embedding_dimensions)} "
        f"latency_ms={latency_ms} status={_safe(status)} "
        f"retry_count={retry_count} error_type={_safe(error_type)}",
    )
