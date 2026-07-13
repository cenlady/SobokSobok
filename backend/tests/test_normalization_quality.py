from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from app.jobs.crawl_policy_sources_loop import _needs_post_extraction_refresh
from app.jobs.evaluate_normalization_quality import evaluate_normalization_quality
from app.services.normalization.documents import (
    _extract_required_documents_from_attachment,
)
from app.services.normalization.field_extractors import _extract_industry_condition
from app.services.normalization.metadata import INDUSTRY_KEYWORDS
from app.services.normalization.regions import _extract_region_metadata
from app.services.normalization.sources import (
    _empty_progress_stats,
    _log_progress,
    _record_progress,
)


class RequiredDocumentQualityTests(unittest.TestCase):
    def test_attachment_requires_explicit_requirement_section(self) -> None:
        text = """
        <html><body>
        <h2>지원내용</h2>
        <p>신청서류 검토 후 지원금을 지급합니다.</p>
        <p>자세한 내용은 홈페이지와 첨부파일을 확인하세요.</p>
        </body></html>
        """

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(documents, [])

    def test_attachment_extracts_document_names_below_heading_only(self) -> None:
        text = """
        <h3>제출서류</h3>
        <table>
          <tr><td>1. 사업자등록증 사본</td></tr>
          <tr><td>2. 개인정보 수집·이용 동의서</td></tr>
        </table>
        <h3>문의처</h3>
        <p>담당자에게 신청서를 제출하시기 바랍니다.</p>
        """

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(
            [item["name"] for item in documents],
            ["사업자등록증 사본", "개인정보 수집·이용 동의서"],
        )
        self.assertTrue(
            all(item["extraction_method"] == "attachment_requirement_section" for item in documents)
        )

    def test_document_name_with_and_is_not_split_mid_name(self) -> None:
        text = "제출서류 : 사업신청서, 신용정보제공 및 활용동의서"

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(
            [item["name"] for item in documents],
            ["사업신청서", "신용정보제공 및 활용동의서"],
        )

    def test_html_and_generic_document_words_do_not_become_names(self) -> None:
        text = """
        <h3>제출서류 안내</h3>
        <p>아래 서류를 온라인으로 제출하시기 바랍니다.</p>
        <p>관련 자료와 기타 서류는 공고문을 확인하세요.</p>
        """

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(documents, [])

    def test_instruction_fragments_are_trimmed_or_rejected(self) -> None:
        text = """
        제출서류
        외부 직원인 경우 원천징수영수증 제출
        ①~③서류 중 택1+본견적서+비교견적서
        ## 개인정보 수집·이용 동의서
        """

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(
            [item["name"] for item in documents],
            ["원천징수영수증", "본견적서", "비교견적서", "개인정보 수집·이용 동의서"],
        )

    def test_leading_number_in_document_name_is_not_a_list_marker(self) -> None:
        text = "제출서류\n4대보험료 완납증명원\n건강보험자격득실확인서"

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual(
            [item["name"] for item in documents],
            ["4대보험료 완납증명원", "건강보험자격득실확인서"],
        )

    def test_residual_instruction_sentences_are_not_document_names(self) -> None:
        text = """
        제출서류
        소상공인 확인서
        납세증명서는 서류에 명시된 유효기간만 가능
        공통서류 제출 (소상공인 확인서 등)
        사업자등록번호
        상시근로자 확인서류
        """

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual([item["name"] for item in documents], ["소상공인 확인서"])

    def test_document_names_are_deduplicated_ignoring_spaces(self) -> None:
        text = "제출서류\n통장사본\n통장 사본"

        documents = _extract_required_documents_from_attachment(text, "sbiz24")

        self.assertEqual([item["name"] for item in documents], ["통장사본"])


class RegionQualityTests(unittest.TestCase):
    def test_eligibility_region_has_high_confidence(self) -> None:
        region = _extract_region_metadata("서울특별시에 사업장을 둔 소상공인")

        self.assertEqual(region["region_scope"], "local")
        self.assertEqual(region["matched_sidos"], ["서울특별시"])
        self.assertGreaterEqual(region["confidence"], 0.9)
        self.assertEqual(region["source_ref"], "eligibility")

    def test_title_only_region_is_low_confidence_fallback(self) -> None:
        region = _extract_region_metadata(None, fallback_text="서울시 소상공인 지원")

        self.assertEqual(region["region_scope"], "local")
        self.assertLess(region["confidence"], 0.8)
        self.assertEqual(region["source_ref"], "title")

    def test_explicit_national_condition_wins_over_local_title(self) -> None:
        region = _extract_region_metadata(
            "전국 소재 소상공인",
            fallback_text="서울시 디지털 전환 지원",
        )

        self.assertEqual(region["region_scope"], "national")
        self.assertEqual(region["condition_mode"], "unrestricted")

    def test_ambiguous_bare_sigungu_is_not_an_eligibility_region(self) -> None:
        region = _extract_region_metadata("양주 제조업체")

        self.assertEqual(region["region_scope"], "unknown")
        self.assertEqual(region["matched_sidos"], [])

    def test_unique_metropolitan_district_maps_to_its_sido(self) -> None:
        region = _extract_region_metadata("동작구 내 사업장을 둔 소상공인")

        self.assertEqual(region["matched_sidos"], ["서울특별시"])
        self.assertEqual(region["sigungu"], "동작구")

    def test_sigungu_with_particle_is_primary_evidence(self) -> None:
        region = _extract_region_metadata("보령시에서 창업을 희망하는 청년")

        self.assertEqual(region["matched_sidos"], ["충청남도"])
        self.assertEqual(region["source_ref"], "eligibility")

    def test_local_currency_brand_is_title_fallback(self) -> None:
        region = _extract_region_metadata(
            "소상공인 및 상품권 구입자",
            fallback_text="지역화폐(당진사랑상품권 가맹점 등록)",
        )

        self.assertEqual(region["matched_sidos"], ["충청남도"])
        self.assertEqual(region["source_ref"], "title")


class IndustryQualityTests(unittest.TestCase):
    def test_program_topic_is_not_treated_as_industry(self) -> None:
        condition = _extract_industry_condition(
            "디지털 전환 교육 지원 대상: 소상공인",
            INDUSTRY_KEYWORDS,
        )

        self.assertEqual(condition["mode"], "unknown")
        self.assertEqual(condition["include_tags"], [])

    def test_explicit_industry_eligibility_is_included(self) -> None:
        condition = _extract_industry_condition(
            "음식점업을 영위하는 소상공인",
            INDUSTRY_KEYWORDS,
        )

        self.assertEqual(condition["include_tags"], ["restaurant"])
        self.assertEqual(condition["exclude_tags"], [])

    def test_explicit_exclusion_is_kept_separately(self) -> None:
        condition = _extract_industry_condition(
            "제조업은 지원 대상에서 제외",
            INDUSTRY_KEYWORDS,
        )

        self.assertEqual(condition["include_tags"], [])
        self.assertEqual(condition["exclude_tags"], ["manufacturing"])

    def test_unrestricted_industry_is_explicit(self) -> None:
        condition = _extract_industry_condition("업종 제한 없음", INDUSTRY_KEYWORDS)

        self.assertEqual(condition["mode"], "unrestricted")
        self.assertGreaterEqual(condition["confidence"], 0.95)

    def test_agriculture_person_is_an_explicit_industry_condition(self) -> None:
        condition = _extract_industry_condition(
            "고창군 농업인 및 생산단체",
            INDUSTRY_KEYWORDS,
        )

        self.assertEqual(condition["include_tags"], ["agriculture_fishery_forestry"])


class PipelineQualityTests(unittest.TestCase):
    def test_post_extraction_refresh_only_when_new_text_was_extracted(self) -> None:
        self.assertTrue(_needs_post_extraction_refresh({"success": 2}))
        self.assertFalse(_needs_post_extraction_refresh({"success": 0}))
        self.assertFalse(_needs_post_extraction_refresh(None))


class NormalizationProgressLogTests(unittest.TestCase):
    def test_progress_stats_summarize_normalized_fields(self) -> None:
        progress = _empty_progress_stats()
        payload = {
            "required_documents": [{"name": "신청서"}, {"name": "사업자등록증"}],
            "eligibility": {
                "region": {"condition_mode": "restricted", "confidence": 0.93},
                "industry_condition": {"mode": "restricted"},
                "llm_cache": {"employee_limit": {"status": "accepted"}},
            },
        }

        _record_progress(progress, payload)

        self.assertEqual(progress["required_documents"], 2)
        self.assertEqual(progress["region_confirmed"], 1)
        self.assertEqual(progress["region_needs_review"], 0)
        self.assertEqual(progress["industry_known"], 1)
        self.assertEqual(progress["llm_cached_fields"], 1)

    def test_progress_log_is_periodic_and_includes_summary(self) -> None:
        action_stats = {
            "normalized_created": 1,
            "normalized_updated": 2,
            "normalized_unchanged": 22,
            "errors": 0,
        }
        field_stats = {
            "required_documents": 7,
            "region_confirmed": 8,
            "region_needs_review": 1,
            "industry_known": 5,
            "llm_cached_fields": 3,
        }

        quiet_output = io.StringIO()
        with redirect_stdout(quiet_output):
            _log_progress(
                source="test",
                processed=24,
                total=50,
                current_title="테스트 공고",
                action_stats=action_stats,
                field_stats=field_stats,
            )
        self.assertEqual(quiet_output.getvalue(), "")

        progress_output = io.StringIO()
        with redirect_stdout(progress_output):
            _log_progress(
                source="test",
                processed=25,
                total=50,
                current_title="테스트 공고",
                action_stats=action_stats,
                field_stats=field_stats,
            )
        output = progress_output.getvalue()
        self.assertIn("[normalizer] test: progress=25/50", output)
        self.assertIn("created=1,updated=2,unchanged=22,errors=0", output)
        self.assertIn("docs=7", output)
        self.assertIn("region_confirmed=8", output)
        self.assertIn("industry_known=5", output)
        self.assertIn("llm_cached=3", output)
        self.assertIn("current='테스트 공고'", output)


class GoldenQualityEvaluationTests(unittest.TestCase):
    def test_actual_policy_gold_fixture_stays_above_quality_floor(self) -> None:
        result = evaluate_normalization_quality()

        self.assertEqual(result["actual_policy_cases"], 50)
        self.assertGreaterEqual(result["region"]["f1"], 0.9)
        self.assertGreaterEqual(result["industry"]["f1"], 0.9)
        self.assertGreaterEqual(result["required_documents"]["f1"], 0.85)


if __name__ == "__main__":
    unittest.main()
