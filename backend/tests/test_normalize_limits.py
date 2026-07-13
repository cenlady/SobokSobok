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

    def test_business_registration_elapsed_is_business_age_lower_bound(self) -> None:
        result = _extract_business_age_limit("사업자등록 후 1년 경과하여 영업 중인 개인기업")
        self.assertEqual(result["value"], 1)
        self.assertEqual(result["operator"], ">=")

    def test_unseen_employee_wording_uses_generic_industry_anchor(self) -> None:
        result = _extract_employee_limit("정보통신업 5인 미만 사업자")
        self.assertEqual(result["value"], 5)
        self.assertEqual(result["operator"], "<")

    def test_unseen_business_age_wording_is_supported(self) -> None:
        result = _extract_business_age_limit("영업기간 3년 이하 기업")
        self.assertEqual(result["value"], 3)
        self.assertEqual(result["operator"], "<=")

    def test_mixed_korean_money_units_are_summed(self) -> None:
        result = _extract_sales_limit("2025년도 매출액 1억 4백만원 미만 소상공인")
        self.assertEqual(result["amount_krw"], 104_000_000)
        self.assertEqual(result["operator"], "<")

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
    def test_llm_does_not_treat_rent_as_sales_lower_bound(self, mock_post) -> None:
        evidence = "연 매출액 1억원 이하 ▸ 월 임차료 30만원 이상"
        mock_post.return_value = FakeOllamaResponse(
            {
                "classification": "direct",
                "logic": "all_of",
                "scope": "global",
                "min": 300_000,
                "min_operator": ">=",
                "max": 100_000_000,
                "max_operator": "<=",
                "evidence": evidence,
            }
        )

        result = _extract_limits_via_ollama(evidence, ["sales_limit"])["sales_limit"]

        self.assertIsNone(result["min_value"])
        self.assertEqual(result["max_value"], 100_000_000)

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

    @patch("app.services.normalize_policies.httpx.post")
    def test_industry_specific_employee_limits_are_not_flattened(self, mock_post) -> None:
        text = "제조업은 상시근로자 10인 미만, 기타 업종은 상시근로자 5인 미만"
        mock_post.return_value = FakeOllamaResponse(
            {"classification": "alternative", "logic": "any_of", "scope": "branch", "evidence": text}
        )
        result = _extract_limits_via_ollama(text, ["employee_limit"])["employee_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual({item["value"] for item in result["constraints"]}, {5, 10})
        self.assertNotIn("value", result)

    @patch("app.services.normalize_policies.httpx.post")
    def test_funding_type_age_limits_are_not_flattened(self, mock_post) -> None:
        text = (
            "자금별 요건을 충족해야 함 - 창업자금 : 업력 1년 이내 "
            "- 경영개선자금 : 업력 1년 초과 - 점포임차자금 : 소상공인"
        )
        mock_post.return_value = FakeOllamaResponse(
            {"classification": "alternative", "logic": "any_of", "scope": "branch", "evidence": text}
        )
        result = _extract_limits_via_ollama(text, ["business_age_limit"])["business_age_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual(result["logic"], "any_of")
        self.assertNotIn("value", result)

    @patch("app.services.normalize_policies.httpx.post")
    def test_or_sales_condition_is_not_flattened(self, mock_post) -> None:
        text = "기준 중위소득 125% 이하 소상공인 또는 최근 1년 연 매출액 2억원 이하 소상공인"
        mock_post.return_value = FakeOllamaResponse(
            {"classification": "alternative", "logic": "any_of", "scope": "branch", "evidence": text}
        )
        result = _extract_limits_via_ollama(text, ["sales_limit"])["sales_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual(result["review_reason"], "alternative")
        self.assertEqual(result["extraction_method"], "ollama_structure")
        self.assertNotIn("amount_krw", result)

    @patch("app.services.normalize_policies.httpx.post")
    def test_mixed_money_is_preserved_inside_complex_payload(self, mock_post) -> None:
        text = (
            "아래 ①~③ 요건을 모두 충족 ① 영업 중 ② 매출액 1억 4백만원 미만 "
            "③ 증빙 가능 ※ 업종별 평균매출액 기준 별도"
        )
        mock_post.return_value = FakeOllamaResponse(
            {"classification": "complex", "logic": "all_of", "scope": "global", "evidence": text}
        )
        result = _extract_limits_via_ollama(text, ["sales_limit"])["sales_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertIn(104_000_000, {item["value"] for item in result["constraints"]})

    @patch("app.services.normalize_policies.httpx.post")
    def test_relational_employee_condition_is_not_flattened(self, mock_post) -> None:
        text = (
            "다음 각 호 중 1개 이상 충족 ① 업력 3년 미만 "
            "② 상시근로자 중 과반수가 청년 ③ 최근 1년 이내 근로자 1인 이상 고용하고 유지"
        )
        mock_post.return_value = FakeOllamaResponse(
            {"classification": "relational", "logic": "any_of", "scope": "branch", "evidence": text}
        )
        result = _extract_limits_via_ollama(text, ["employee_limit"])["employee_limit"]
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual(result["logic"], "any_of")
        self.assertNotIn("value", result)


if __name__ == "__main__":
    unittest.main()
