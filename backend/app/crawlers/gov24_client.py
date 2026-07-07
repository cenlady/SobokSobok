from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote

import httpx

from app.core.config import settings


class Gov24Client:
    """Client for Gov24 public service Open API endpoints."""

    SERVICE_LIST_PATH = "gov24/v3/serviceList"
    SERVICE_DETAIL_PATH = "gov24/v3/serviceDetail"
    SUPPORT_CONDITIONS_PATH = "gov24/v3/supportConditions"

    def __init__(self, timeout: float = 30.0):
        if not settings.GOV24_SERVICE_KEY:
            raise ValueError("GOV24_SERVICE_KEY must be set before running the Gov24 ingest job.")

        base_url = settings.GOV24_BASE_URL.rstrip("/") + "/"
        self._service_key = unquote(settings.GOV24_SERVICE_KEY)
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Gov24Client":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_service_lists(self) -> list[dict[str, Any]]:
        extra_params = {}
        if settings.GOV24_SERVICE_LIST_USER_TYPE_LIKE:
            extra_params["cond[사용자구분::LIKE]"] = settings.GOV24_SERVICE_LIST_USER_TYPE_LIKE
        return self.fetch_all(self.SERVICE_LIST_PATH, extra_params=extra_params)

    def fetch_service_details(self) -> list[dict[str, Any]]:
        return self.fetch_all(self.SERVICE_DETAIL_PATH)

    def fetch_support_conditions(self) -> list[dict[str, Any]]:
        return self.fetch_all(self.SUPPORT_CONDITIONS_PATH)

    def fetch_all(self, path: str, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = settings.GOV24_PAGE_START

        for _ in range(settings.GOV24_MAX_PAGES):
            payload = self.fetch_page(
                path=path,
                page=page,
                per_page=settings.GOV24_PAGE_SIZE,
                extra_params=extra_params,
            )
            items = payload.get("data")
            if not isinstance(items, list) or not items:
                break

            rows.extend(item for item in items if isinstance(item, dict))
            total_count = _as_int(payload.get("totalCount"))
            if total_count is not None and len(rows) >= total_count:
                break
            if len(items) < settings.GOV24_PAGE_SIZE:
                break

            page += 1
            if settings.GOV24_REQUEST_DELAY_SECONDS > 0:
                time.sleep(settings.GOV24_REQUEST_DELAY_SECONDS)

        return rows

    def fetch_page(
        self,
        path: str,
        page: int,
        per_page: int,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = {
            "page": page,
            "perPage": per_page,
            "returnType": "JSON",
            "serviceKey": self._service_key,
        }
        if extra_params:
            params.update(extra_params)

        response = self._client.get(
            path,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Gov24 response must be a JSON object: {path}")
        return payload


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
