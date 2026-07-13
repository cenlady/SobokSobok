import json
import unittest
from unittest.mock import patch

from app.services.normalize_policies import (
    _extract_business_age_limit,
    _extract_employee_limit,
    _extract_limits_via_ollama,
    _extract_sales_limit,
    _limit_fields_requiring_llm,
)


class FakeOllamaResponse:
    def __init__(self, content: dict):
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": json.dumps(self._content, ensure_ascii=False)}}


class NormalizeLimitTests(unittest.TestCase):
    def test_small_business_word_does_not_create_employee_limit(self) -> None:
        self.assertIsNone(_extract_employee_limit("지원대상: 소상공인 및 소기업"))

    def test_llm_is_not_requested_when_numeric_condition_is_absent(self) -> None:
        parsed = {
            "employee_limit": None,
            "sales_limit": None,
            "business_age_limit": None,
        }
        self.assertEqual(_limit_fields_requiring_llm("지원대상: 소상공인", parsed), [])
        self.assertEqual(
            _limit_fields_requiring_llm("지원대상: 상시근로자 약 5명 규모", parsed),
            ["employee_limit"],
        )
        self.assertEqual(
            _limit_fields_requiring_llm("상시종업원 10인 미만 업체", parsed),
            ["employee_limit"],
        )

    def test_business_age_rule_supports_lower_bound(self) -> None:
        result = _extract_business_age_limit("지원대상은 창업 3년 이상 기업")
        self.assertEqual(result["value"], 3)
        self.assertEqual(result["operator"], ">=")

    @patch("app.services.normalize_policies.httpx.post")
    def test_llm_preserves_strict_upper_bound(self, mock_post) -> None:
        evidence = "상시근로자 5인 미만"
        mock_post.return_value = FakeOllamaResponse(
            {
                "employee_limit": {
                    "min": None,
                    "min_operator": None,
                    "max": 5,
                    "max_operator": "<",
                    "evidence": evidence,
                }
            }
        )
        result = _extract_limits_via_ollama(f"지원대상: {evidence}", ["employee_limit"])
        self.assertEqual(result["employee_limit"]["value"], 5)
        self.assertEqual(result["employee_limit"]["operator"], "<")

    @patch("app.services.normalize_policies.httpx.post")
    def test_llm_preserves_two_sided_range_without_flattening(self, mock_post) -> None:
        evidence = "창업 3년 이상 7년 이하"
        mock_post.return_value = FakeOllamaResponse(
            {
                "business_age_limit": {
                    "min": 3,
                    "min_operator": ">=",
                    "max": 7,
                    "max_operator": "<=",
                    "evidence": evidence,
                }
            }
        )
        result = _extract_limits_via_ollama(f"지원대상: {evidence}", ["business_age_limit"])
        limit = result["business_age_limit"]
        self.assertEqual(limit["min_value"], 3)
        self.assertEqual(limit["max_value"], 7)
        self.assertNotIn("value", limit)

    @patch("app.services.normalize_policies.httpx.post")
    def test_evidence_recovers_range_bound_omitted_by_small_model(self, mock_post) -> None:
        evidence = "창업 3년 이상 7년 이하"
        mock_post.return_value = FakeOllamaResponse(
            {
                "min": None,
                "min_operator": None,
                "max": 7,
                "max_operator": "<=",
                "evidence": evidence,
            }
        )
        result = _extract_limits_via_ollama(f"지원대상: {evidence}", ["business_age_limit"])
        limit = result["business_age_limit"]
        self.assertEqual(limit["min_value"], 3)
        self.assertEqual(limit["min_operator"], ">=")
        self.assertEqual(limit["max_value"], 7)
        self.assertNotIn("value", limit)

    @patch("app.services.normalize_policies.httpx.post")
    def test_llm_rejects_evidence_for_a_different_field(self, mock_post) -> None:
        evidence = "상시종업원 10인 미만 업체"
        mock_post.return_value = FakeOllamaResponse(
            {
                "min": None,
                "min_operator": None,
                "max": 10,
                "max_operator": "<=",
                "evidence": evidence,
            }
        )
        result = _extract_limits_via_ollama(
            f"매출 범위 확인 필요. {evidence}",
            ["sales_limit"],
        )
        self.assertIsNone(result["sales_limit"])

    def test_sales_exclusion_is_inverted_to_eligible_range(self) -> None:
        result = _extract_sales_limit("전년도 전체 매출액 100억원 이상인 업소 제외")
        self.assertEqual(result["amount_krw"], 10_000_000_000)
        self.assertEqual(result["operator"], "<")

    def test_generic_failure_notice_does_not_invert_limit(self) -> None:
        result = _extract_employee_limit("상시근로자 5인 미만 업체 (범위 미충족 시 지원 불가)")
        self.assertEqual(result["value"], 5)
        self.assertEqual(result["operator"], "<")

    def test_industry_specific_employee_limits_are_not_flattened(self) -> None:
        text = "제조업은 상시근로자 10인 미만, 기타 업종은 상시근로자 5인 미만"
        result = _extract_limits_via_ollama(text, ["employee_limit"])["employee_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual({item["value"] for item in result["constraints"]}, {5, 10})
        self.assertNotIn("value", result)


if __name__ == "__main__":
    unittest.main()
