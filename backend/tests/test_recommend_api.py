import unittest
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


def _result(status: str) -> RecommendationResult:
    return RecommendationResult(
        policy_id=uuid4(),
        title=f"{status} 정책",
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
