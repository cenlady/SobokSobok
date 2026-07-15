import unittest
from datetime import date, datetime
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.api.v1.calendar import _resolve_coaching_dates, get_google_calendar_events


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, response: _FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, *args, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


class CalendarCoachingDateTests(unittest.TestCase):
    def test_default_target_is_actual_deadline(self) -> None:
        actual, target = _resolve_coaching_dates(
            datetime(2026, 7, 31, 18, 0),
            None,
            today=date(2026, 7, 15),
        )

        self.assertEqual(actual, date(2026, 7, 31))
        self.assertEqual(target, actual)

    def test_earlier_preparation_target_is_allowed(self) -> None:
        actual, target = _resolve_coaching_dates(
            date(2026, 7, 31),
            "2026-07-25",
            today=date(2026, 7, 15),
        )

        self.assertEqual(actual, date(2026, 7, 31))
        self.assertEqual(target, date(2026, 7, 25))

    def test_target_after_actual_deadline_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _resolve_coaching_dates(
                date(2026, 7, 31),
                "2026-08-01",
                today=date(2026, 7, 15),
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("실제 신청 마감일", raised.exception.detail)

    def test_past_policy_and_invalid_target_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as past_policy:
            _resolve_coaching_dates(
                date(2026, 7, 14),
                None,
                today=date(2026, 7, 15),
            )
        self.assertEqual(past_policy.exception.status_code, 400)

        with self.assertRaises(HTTPException) as invalid_target:
            _resolve_coaching_dates(
                date(2026, 7, 31),
                "07/20/2026",
                today=date(2026, 7, 15),
            )
        self.assertEqual(invalid_target.exception.status_code, 400)


class GoogleCalendarEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_empty_calendar_returns_empty_list(self) -> None:
        client = _FakeAsyncClient(response=_FakeResponse(200, {"items": []}))

        with patch("app.api.v1.calendar.httpx.AsyncClient", return_value=client):
            result = await get_google_calendar_events("token")

        self.assertEqual(result, [])

    async def test_successful_response_parses_policy_event(self) -> None:
        policy_id = "cc5bd7f2-d059-458f-9671-639094251121"
        payload = {
            "items": [
                {
                    "summary": "정책 마감",
                    "description": f"● 지원사업ID: {policy_id}",
                    "start": {"date": "2026-07-31"},
                    "end": {"date": "2026-08-01"},
                }
            ]
        }
        client = _FakeAsyncClient(response=_FakeResponse(200, payload))

        with patch("app.api.v1.calendar.httpx.AsyncClient", return_value=client):
            result = await get_google_calendar_events("token")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-07-31")
        self.assertEqual(result[0]["policy_id"], policy_id)

    async def test_google_error_is_not_treated_as_empty_calendar(self) -> None:
        client = _FakeAsyncClient(response=_FakeResponse(500, {"error": "failed"}))

        with (
            patch("app.api.v1.calendar.httpx.AsyncClient", return_value=client),
            self.assertRaises(HTTPException) as raised,
        ):
            await get_google_calendar_events("token")

        self.assertEqual(raised.exception.status_code, 502)

    async def test_permission_error_and_timeout_are_distinguished(self) -> None:
        forbidden_client = _FakeAsyncClient(response=_FakeResponse(403, {}))
        with (
            patch("app.api.v1.calendar.httpx.AsyncClient", return_value=forbidden_client),
            self.assertRaises(HTTPException) as forbidden,
        ):
            await get_google_calendar_events("token")
        self.assertEqual(forbidden.exception.status_code, 403)

        timeout_client = _FakeAsyncClient(error=httpx.ReadTimeout("timeout"))
        with (
            patch("app.api.v1.calendar.httpx.AsyncClient", return_value=timeout_client),
            self.assertRaises(HTTPException) as timeout,
        ):
            await get_google_calendar_events("token")
        self.assertEqual(timeout.exception.status_code, 504)

    async def test_malformed_google_payload_returns_gateway_error(self) -> None:
        client = _FakeAsyncClient(response=_FakeResponse(200, {"items": {}}))

        with (
            patch("app.api.v1.calendar.httpx.AsyncClient", return_value=client),
            self.assertRaises(HTTPException) as raised,
        ):
            await get_google_calendar_events("token")

        self.assertEqual(raised.exception.status_code, 502)
