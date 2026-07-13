from datetime import datetime
from unittest.mock import ANY, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.policies import router
from app.core.database import get_db
from app.schemas.policy import NormalizedPolicyListRead


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/policies")

    def override_get_db():
        return object()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _policy() -> NormalizedPolicyListRead:
    return NormalizedPolicyListRead(
        id=uuid4(),
        title="소상공인 신용보증 지원",
        summary="신용보증 지원 안내",
        organization="소상공인시장진흥공단",
        support_type="금융",
        region_scope="national",
        status="접수중",
        apply_start=datetime(2026, 7, 1),
        apply_end=datetime(2026, 8, 31),
        apply_url="https://example.com/apply",
    )


def test_normalized_policy_list_returns_lightweight_items_and_forwards_filters():
    with patch(
        "app.api.v1.policies.list_normalized_policies",
        return_value=([_policy()], 41),
    ) as list_policies:
        response = _client().get(
            "/policies/normalized/?skip=20&limit=30&q=신용보증&support_type=금융&sido=서울특별시"
            "&category=funding&status=available&sort=deadline"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["title"] == "소상공인 신용보증 지원"
    assert body["total"] == 41
    assert body["has_next"] is True
    list_policies.assert_called_once_with(
        ANY,
        skip=20,
        limit=30,
        q="신용보증",
        support_type="금융",
        sido="서울특별시",
        category="funding",
        status="available",
        sort="deadline",
    )


def test_normalized_list_route_is_not_captured_by_legacy_integer_route():
    with patch("app.api.v1.policies.list_normalized_policies", return_value=([], 0)):
        response = _client().get("/policies/normalized/")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "skip": 0,
        "limit": 20,
        "has_next": False,
    }


def test_normalized_list_limit_is_validated():
    with patch("app.api.v1.policies.list_normalized_policies") as list_policies:
        response = _client().get("/policies/normalized/?limit=101")

    assert response.status_code == 422
    list_policies.assert_not_called()


def test_normalized_list_rejects_unknown_category_and_sort():
    with patch("app.api.v1.policies.list_normalized_policies") as list_policies:
        category_response = _client().get("/policies/normalized/?category=unknown")
        sort_response = _client().get("/policies/normalized/?sort=popular")

    assert category_response.status_code == 422
    assert sort_response.status_code == 422
    list_policies.assert_not_called()
