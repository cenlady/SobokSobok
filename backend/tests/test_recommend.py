from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import app.services.recommend as recommend_service
from app.core.model_errors import ModelTimeoutError
from app.schemas.recommend import NumberRangeInput, RecommendationProfileRequest, RegionInput
from app.services.recommend import (
    evaluate_policy,
    explain_policy_recommendation,
    profile_validation_warnings,
    recommend_policies,
)


def make_policy(**overrides):
    values = {
        "id": uuid4(),
        "source": "sbiz24",
        "source_pk": str(uuid4()),
        "duplicate_group_key": str(uuid4()),
        "title": "소상공인 자금 지원",
        "summary": "소상공인의 경영안정을 위한 자금 지원",
        "organization": "지원기관",
        "support_type": "현금(융자)",
        "target_text": "운영 중인 소상공인",
        "support_content": "운영자금을 지원합니다.",
        "region_scope": "national",
        "sido": None,
        "sigungu": None,
        "matched_sidos": [],
        "status": "open",
        "apply_start": None,
        "apply_end": None,
        "apply_url": "https://example.com",
        "application_methods": [],
        "contact_points": [],
        "required_documents": [],
        "industry_tags": ["restaurant"],
        "business_status_tags": ["small_business", "operating_business"],
        "employee_limit_value": None,
        "employee_limit_operator": None,
        "sales_limit_amount_krw": None,
        "sales_limit_operator": None,
        "business_age_limit_value": None,
        "business_age_limit_operator": None,
        "eligibility": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_profile(**overrides):
    values = {
        "region": RegionInput(sido="서울특별시", sigungu="마포구"),
        "industry_tags": ["restaurant"],
        "business_status_tags": ["small_business", "operating_business"],
        "employees": 4,
        "annual_sales_krw": 300_000_000,
        "business_age_years": 2,
        "need_tags": ["funding"],
        "use_vectors": False,
    }
    values.update(overrides)
    return RecommendationProfileRequest(**values)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, policies):
        self.policies = policies

    def query(self, model):
        return FakeQuery(self.policies)


class FakeExplainSession:
    def __init__(self, policy):
        self.policy = policy

    def get(self, model, policy_id):
        return self.policy if self.policy.id == policy_id else None


class RecommendationTests(unittest.TestCase):
    def test_model_timeout_is_not_replaced_with_rule_explanation(self) -> None:
        policy = make_policy(
            title="교육 지원",
            summary="소상공인 교육 지원",
            support_type="교육",
            support_content="역량강화 교육을 지원합니다.",
        )
        profile = make_profile(need_tags=["funding"])

        with patch.object(recommend_service, "get_chat_model") as mock_get_chat_model:
            mock_get_chat_model.return_value.generate.side_effect = ModelTimeoutError()
            with self.assertRaises(ModelTimeoutError):
                explain_policy_recommendation(
                    FakeExplainSession(policy),
                    policy.id,
                    profile,
                )

    def test_sigungu_mismatch_is_ineligible(self) -> None:
        policy = make_policy(
            region_scope="local",
            sido="서울특별시",
            sigungu="광진구",
            matched_sidos=["서울특별시"],
        )

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")
        self.assertTrue(any("광진구" in reason for reason in evaluation.failed))

    def test_local_policy_with_missing_region_is_needs_review(self) -> None:
        policy = make_policy(region_scope="local", sido=None, matched_sidos=[])

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "needs_review")
        self.assertIn("정책 대상 지역", evaluation.unknown_conditions)

    def test_clear_numeric_mismatch_is_ineligible(self) -> None:
        policy = make_policy(employee_limit_value=5, employee_limit_operator="<")

        evaluation = evaluate_policy(policy, make_profile(employees=5))

        self.assertEqual(evaluation.status, "ineligible")
        self.assertTrue(any("직원수" in reason for reason in evaluation.failed))

    def test_open_ended_user_range_is_needs_review_not_exact_match(self) -> None:
        policy = make_policy(employee_limit_value=10, employee_limit_operator="<=")
        profile = make_profile(employees=NumberRangeInput(min=10, max=None))

        evaluation = evaluate_policy(policy, profile)

        self.assertEqual(evaluation.status, "needs_review")
        self.assertIn("직원수", evaluation.unknown_conditions)

    def test_two_sided_limit_from_eligibility_json_is_applied(self) -> None:
        policy = make_policy(
            eligibility={
                "business_age_limit": {
                    "min_value": 3,
                    "min_operator": ">=",
                    "max_value": 7,
                    "max_operator": "<=",
                }
            }
        )

        accepted = evaluate_policy(policy, make_profile(business_age_years=5))
        rejected = evaluate_policy(policy, make_profile(business_age_years=8))

        self.assertEqual(accepted.status, "eligible")
        self.assertEqual(rejected.status, "ineligible")

    def test_manual_review_numeric_condition_never_hard_rejects(self) -> None:
        policy = make_policy(
            employee_limit_value=1,
            employee_limit_operator=">=",
            eligibility={
                "employee_limit": {
                    "constraints": [{"value": 1, "operator": ">="}],
                    "logic": "any_of",
                    "requires_manual_review": True,
                    "review_reason": "branching_condition",
                }
            },
        )

        evaluation = evaluate_policy(policy, make_profile(employees=0))

        self.assertEqual(evaluation.status, "needs_review")
        self.assertIn("직원수", evaluation.unknown_conditions)
        self.assertFalse(any("직원수" in reason for reason in evaluation.failed))

    def test_unparsed_numeric_condition_requires_review(self) -> None:
        policy = make_policy(
            eligibility={
                "employee_limit": {
                    "source_text": "업종별 상시근로자 기준 적용",
                    "extraction_method": "rule",
                }
            }
        )

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "needs_review")
        self.assertIn("직원수", evaluation.unknown_conditions)

    def test_direct_numeric_json_condition_is_applied_without_flat_column(self) -> None:
        policy = make_policy(
            eligibility={
                "sales_limit": {
                    "amount_krw": 100_000_000,
                    "operator": "<=",
                    "source_text": "연매출 1억원 이하",
                }
            }
        )

        evaluation = evaluate_policy(policy, make_profile(annual_sales_krw=200_000_000))

        self.assertEqual(evaluation.status, "ineligible")
        self.assertTrue(any("연매출" in reason for reason in evaluation.failed))

    def test_any_of_numeric_constraints_accepts_one_matching_branch(self) -> None:
        policy = make_policy(
            eligibility={
                "business_age_limit": {
                    "min_value": 3,
                    "min_operator": ">=",
                    "max_value": 1,
                    "max_operator": "<=",
                    "logic": "any_of",
                }
            }
        )

        young_branch = evaluate_policy(policy, make_profile(business_age_years=1))
        mature_branch = evaluate_policy(policy, make_profile(business_age_years=4))
        no_branch = evaluate_policy(policy, make_profile(business_age_years=2))

        self.assertEqual(young_branch.status, "eligible")
        self.assertEqual(mature_branch.status, "eligible")
        self.assertEqual(no_branch.status, "ineligible")

    def test_industry_mismatch_is_near_match(self) -> None:
        policy = make_policy(industry_tags=["manufacturing"])

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "near_match")
        self.assertTrue(evaluation.soft_mismatches)

    def test_selected_need_without_match_is_near_match(self) -> None:
        policy = make_policy(
            title="교육 지원",
            summary="소상공인 역량강화 교육",
            support_type="교육",
            support_content="교육과 컨설팅을 지원합니다.",
        )

        evaluation = evaluate_policy(policy, make_profile(need_tags=["funding"]))

        self.assertEqual(evaluation.status, "near_match")
        self.assertEqual(evaluation.eligibility_status, "eligible")
        self.assertEqual(evaluation.preference_match, "none")
        self.assertTrue(any("관심 분야" in reason for reason in evaluation.preference_mismatches))

    def test_eligibility_warning_is_not_hidden_by_preference_mismatch(self) -> None:
        policy = make_policy(
            title="교육 지원",
            summary="소상공인 교육",
            support_type="교육",
            support_content="역량강화 교육을 지원합니다.",
            region_scope="unknown",
        )

        evaluation = evaluate_policy(policy, make_profile(need_tags=["funding"]))

        self.assertEqual(evaluation.eligibility_status, "needs_review")
        self.assertEqual(evaluation.preference_match, "none")
        self.assertEqual(evaluation.status, "needs_review")

    def test_low_confidence_title_region_never_hard_rejects(self) -> None:
        policy = make_policy(
            region_scope="local",
            sido="부산광역시",
            matched_sidos=["부산광역시"],
            region_confidence=0.68,
            eligibility={
                "region": {
                    "condition_mode": "restricted",
                    "confidence": 0.68,
                    "source_ref": "title",
                }
            },
        )

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "needs_review")
        self.assertFalse(any("지역 조건이 맞지" in reason for reason in evaluation.failed))

    def test_explicit_excluded_industry_is_ineligible(self) -> None:
        policy = make_policy(
            industry_tags=[],
            eligibility={
                "industry_condition": {
                    "mode": "restricted",
                    "include_tags": [],
                    "exclude_tags": ["restaurant"],
                    "confidence": 0.9,
                }
            },
        )

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")
        self.assertTrue(any("제외 업종" in reason for reason in evaluation.failed))

    def test_explicit_unrestricted_industry_is_eligible(self) -> None:
        policy = make_policy(
            industry_tags=[],
            eligibility={
                "industry_condition": {
                    "mode": "unrestricted",
                    "include_tags": [],
                    "exclude_tags": [],
                    "confidence": 0.98,
                }
            },
        )

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "eligible")
        self.assertTrue(any("업종 제한이 없는" in reason for reason in evaluation.reasons))

    def test_operating_business_does_not_match_pre_founder_only_policy(self) -> None:
        policy = make_policy(business_status_tags=["pre_founder"])

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")

    def test_scale_match_does_not_hide_lifecycle_mismatch(self) -> None:
        policy = make_policy(business_status_tags=["pre_founder", "small_business"])

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")
        self.assertTrue(any("운영 상태" in reason for reason in evaluation.failed))

    def test_small_business_profile_employee_conflict_is_reported(self) -> None:
        warnings = profile_validation_warnings(
            make_profile(employees=NumberRangeInput(min=10, max=None))
        )

        self.assertTrue(any("소상공인 선택이 충돌" in warning for warning in warnings))

    def test_missing_vector_score_does_not_beat_known_similarity(self) -> None:
        scored = make_policy(title="벡터 점수 있음")
        missing = make_policy(title="벡터 점수 없음")
        profile = make_profile(use_vectors=True)

        with patch.object(
            recommend_service,
            "_vector_scores",
            return_value=({scored.id: 0.4}, True),
        ):
            results, vector_used, _ = recommend_policies(
                FakeSession([missing, scored]),
                profile,
                limit=10,
            )

        self.assertTrue(vector_used)
        self.assertEqual(results[0].title, "벡터 점수 있음")
        self.assertEqual(results[1].score_breakdown["semantic_similarity"], 0.0)

    def test_korean_policy_clock_controls_deadline_boundary(self) -> None:
        policy = make_policy(apply_end=datetime(2026, 7, 13, 23, 59, 59))

        with patch.object(
            recommend_service,
            "korea_now_naive",
            return_value=datetime(2026, 7, 14, 0, 0, 1),
        ):
            evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")

    def test_closed_policy_is_ineligible_even_when_evaluated_directly(self) -> None:
        policy = make_policy(status="closed", apply_end=datetime.now() - timedelta(days=1))

        evaluation = evaluate_policy(policy, make_profile())

        self.assertEqual(evaluation.status, "ineligible")

    def test_results_are_tiered_and_duplicate_groups_are_collapsed(self) -> None:
        duplicate_key = "same-policy"
        eligible = make_policy(duplicate_group_key=duplicate_key, title="정확히 맞는 정책")
        duplicate = make_policy(duplicate_group_key=duplicate_key, title="중복 정책")
        near_match = make_policy(
            duplicate_group_key="different-policy",
            title="유사 정책",
            industry_tags=["manufacturing"],
        )

        results, vector_used, total = recommend_policies(
            FakeSession([near_match, duplicate, eligible]),
            make_profile(),
            limit=10,
        )

        self.assertFalse(vector_used)
        self.assertEqual(total, 2)
        self.assertEqual(results[0].match_status, "eligible")
        self.assertEqual(results[1].match_status, "near_match")
        self.assertEqual({result.title for result in results} & {"정확히 맞는 정책", "중복 정책"}, {results[0].title})
        self.assertTrue(results[0].score_breakdown)


if __name__ == "__main__":
    unittest.main()
