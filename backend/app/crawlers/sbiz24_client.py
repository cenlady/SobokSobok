from __future__ import annotations

from typing import Any

import httpx


class Sbiz24Client:
    """Small client for the Sbiz24 frontend API used by the public site."""

    BASE_URL = "https://www.sbiz24.kr"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin-Method": "GET",
                "Referer": "https://www.sbiz24.kr/",
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

    def __enter__(self) -> "Sbiz24Client":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _post_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.post(path, json=payload or {})
        response.raise_for_status()
        data = response.json()
        if data.get("result") is False:
            raise RuntimeError(f"Sbiz24 API returned result=false for {path}: {data}")
        return data

    def fetch_list_page(self, start: int, end: int) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        # 사이트 화면에서 선택한 필터: 지원대상=소상공인, 신청가능, 분류=공단지원사업.
        payload = {
            "sortModel": [],
            "search": {
                "rcrtTypeCdNmList": ["소상공인"],
                "rcrtTypeCdNmListDisplay": "소상공인",
                "aplySeYn": "Y",
                "sbrPbancYn": "N",
                "itrstPbancYn": "N",
                "bizType": "A",
            },
            "paging": True,
            "startRow": start,
            "endRow": end,
        }
        raw = self._post_json("/api/combinePbanc/list", payload)
        data = raw.get("data") or {}
        default = data.get("default") or {}

        if data.get("list"):
            rows = data.get("list") or []
            total_value = data.get("total") or default.get("totalElements")
        elif isinstance(default, dict) and default.get("list"):
            rows = default.get("list") or []
            total_value = default.get("total") or default.get("totalElements")
        else:
            rows = []
            total_value = data.get("total") or default.get("totalElements")

        total = int(total_value or len(rows))
        return rows, total, raw

    def fetch_announcements(self, page_size: int = 100) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        announcements: list[tuple[dict[str, Any], dict[str, Any]]] = []
        start = 0

        while True:
            # 전체 목록을 페이지 단위로 읽고, 중복/변경 여부는 저장 단계에서 판단한다.
            rows, total, raw = self.fetch_list_page(start=start, end=start + page_size)
            if not rows:
                break

            for row in rows:
                announcements.append((row, row))

            start += page_size
            if start >= total:
                break

        return announcements

    def fetch_detail(self, pbanc_sn: int) -> dict[str, Any]:
        return self._post_json(f"/api/pbanc/{pbanc_sn}", {})

    def fetch_attachment_metadata(self, pbanc_sn: int) -> dict[str, Any]:
        # Sbiz24 첨부파일은 공고 번호를 포함한 groupId로 조회된다.
        payload = {
            "search": {
                "groupId": f"pbancdoc-{pbanc_sn}",
                "tmprStrgYn": "N",
                "delYn": False,
            }
        }
        return self._post_json("/api/cmmn/file", payload)

    def download_attachment(self, file_id: str) -> bytes:
        response = self._client.post(f"/api/cmmn/file/{file_id}", json={})
        response.raise_for_status()
        return response.content
