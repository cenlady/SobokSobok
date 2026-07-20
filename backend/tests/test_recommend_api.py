import unittest
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.recommend import router
from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.recommend import RecommendationResult


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/recommend")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: object()
    return TestClient(app)


def _result(
    status: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    support_content: str | None = None,
    apply_start: datetime | None = None,
    apply_end: datetime | None = None,
    apply_status: str | None = None,
) -> RecommendationResult:
    return RecommendationResult(
        policy_id=uuid4(),
        title=title or f"{status} 정책",
        summary=summary,
        support_content=support_content,
        apply_start=apply_start,
        apply_end=apply_end,
        status=apply_status,
        eligibility_status="needs_review" if status == "needs_review" else "eligible",
        preference_match="none" if status == "near_match" else "exact",
        match_status=status,
        confidence="medium",
        rank_score=1.0,
    )


class RecommendationApiTests(unittest.TestCase):
    def test_preview_rejects_out_of_scope_source_query_before_embedding(self):
        with patch("app.api.v1.recommend.recommend_policies") as recommend_mock:
            response = _client().post(
                "/recommend/preview",
                params={"source_query": "소상공인이 신청할 수 있는 넷플릭스 추천해줘"},
                json={},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "정책 추천과 관련된 질문을 입력해 주세요.")
        recommend_mock.assert_not_called()

    def test_preview_accepts_multiple_status_filters_and_returns_their_union(self):
        results = [_result("eligible"), _result("needs_review"), _result("near_match")]
        with (
            patch("app.api.v1.recommend.recommend_policies", return_value=(results, False, 3)),
            patch("app.api.v1.recommend.profile_validation_warnings", return_value=[]),
        ):
            response = _client().post(
                "/recommend/preview?status=eligible&status=near_match&limit=12",
                json={},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["filtered_candidates"], 2)
        self.assertEqual(body["returned"], 2)
        self.assertEqual(
            {item["match_status"] for item in body["results"]},
            {"eligible", "near_match"},
        )
        self.assertEqual(
            body["status_counts"],
            {"eligible": 1, "needs_review": 1, "near_match": 1},
        )

    def test_preview_filters_by_schedule_without_changing_status_filter_contract(self):
        results = [
            _result(
                "needs_review",
                apply_start=datetime(2026, 7, 13),
                apply_end=datetime(2026, 7, 27),
                apply_status="open",
            ),
            _result("eligible", apply_status="open"),
            _result("near_match", apply_status="notice"),
        ]
        with (
            patch("app.api.v1.recommend.recommend_policies", return_value=(results, False, 3)),
            patch("app.api.v1.recommend.profile_validation_warnings", return_value=[]),
        ):
            response = _client().post("/recommend/preview?schedule=period", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["filtered_candidates"], 1)
        self.assertEqual(body["returned"], 1)
        self.assertEqual(body["results"][0]["match_status"], "needs_review")
        self.assertEqual(
            body["schedule_counts"],
            {"period": 1, "ongoing": 1, "unknown": 1},
        )

    def test_preview_accepts_multiple_schedule_filters(self):
        results = [
            _result(
                "eligible",
                apply_start=datetime(2026, 7, 13),
                apply_end=datetime(2026, 7, 27),
                apply_status="open",
            ),
            _result("needs_review", apply_status="open"),
            _result("near_match", apply_status="notice"),
        ]
        with (
            patch("app.api.v1.recommend.recommend_policies", return_value=(results, False, 3)),
            patch("app.api.v1.recommend.profile_validation_warnings", return_value=[]),
        ):
            response = _client().post(
                "/recommend/preview?schedule=period&schedule=unknown",
                json={},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filtered_candidates"], 2)

    def test_preview_searches_recommendations_before_schedule_filter_and_pagination(self):
        results = [
            _result(
                "eligible",
                title="소상공인 온라인 판로 지원",
                support_content="온라인 쇼핑몰 입점과 홍보 비용을 지원합니다.",
                apply_status="open",
            ),
            _result(
                "needs_review",
                title="경영 컨설팅",
                support_content="매장 운영 진단을 지원합니다.",
                apply_start=datetime(2026, 7, 13),
                apply_end=datetime(2026, 7, 27),
                apply_status="open",
            ),
            _result(
                "near_match",
                title="시설 개선",
                support_content="장비 교체 비용을 지원합니다.",
                apply_status="open",
            ),
        ]
        with (
            patch("app.api.v1.recommend.recommend_policies", return_value=(results, False, 3)),
            patch("app.api.v1.recommend.profile_validation_warnings", return_value=[]),
        ):
            response = _client().post("/recommend/preview?q=온라인&schedule=ongoing&limit=12", json={})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_candidates"], 1)
        self.assertEqual(body["filtered_candidates"], 1)
        self.assertEqual(body["schedule_counts"], {"period": 0, "ongoing": 1, "unknown": 0})
        self.assertEqual(body["results"][0]["title"], "소상공인 온라인 판로 지원")
