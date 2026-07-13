from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.normalization.documents import _extract_required_documents_from_attachment
from app.services.normalization.field_extractors import _extract_industry_condition
from app.services.normalization.metadata import INDUSTRY_KEYWORDS
from app.services.normalization.regions import _extract_region_metadata

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "normalization_gold_cases.json"
)


def evaluate_normalization_quality(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    region_mode_correct = 0
    industry_mode_correct = 0
    region_counts = _empty_counts()
    industry_counts = _empty_counts()
    document_counts = _empty_counts()
    document_case_count = 0
    mismatches: list[dict[str, Any]] = []

    for case in cases:
        region = _extract_region_metadata(
            case.get("eligibility_text"),
            default_scope=case.get("default_scope", "unknown"),
            fallback_text=case.get("title"),
        )
        industry = _extract_industry_condition(
            case.get("eligibility_text"),
            INDUSTRY_KEYWORDS,
        )

        expected_region = case["expected_region"]
        expected_industry = case["expected_industry"]
        actual_region_mode = region.get("condition_mode", "unknown")
        actual_industry_mode = industry.get("mode", "unknown")
        region_mode_correct += int(actual_region_mode == expected_region["mode"])
        industry_mode_correct += int(actual_industry_mode == expected_industry["mode"])
        _update_counts(
            region_counts,
            set(region.get("matched_sidos") or []),
            set(expected_region.get("matched_sidos") or []),
        )
        _update_counts(
            industry_counts,
            {
                *(f"include:{tag}" for tag in industry.get("include_tags") or []),
                *(f"exclude:{tag}" for tag in industry.get("exclude_tags") or []),
            },
            {
                *(f"include:{tag}" for tag in expected_industry.get("include_tags") or []),
                *(f"exclude:{tag}" for tag in expected_industry.get("exclude_tags") or []),
            },
        )

        case_mismatch: dict[str, Any] = {
            "id": case["id"],
            "source_pk": case["source_pk"],
        }
        if actual_region_mode != expected_region["mode"] or set(
            region.get("matched_sidos") or []
        ) != set(expected_region.get("matched_sidos") or []):
            case_mismatch["region"] = {
                "expected": expected_region,
                "actual": {
                    "mode": actual_region_mode,
                    "matched_sidos": region.get("matched_sidos") or [],
                },
            }
        if actual_industry_mode != expected_industry["mode"] or set(
            industry.get("include_tags") or []
        ) != set(expected_industry.get("include_tags") or []) or set(
            industry.get("exclude_tags") or []
        ) != set(expected_industry.get("exclude_tags") or []):
            case_mismatch["industry"] = {
                "expected": expected_industry,
                "actual": {
                    "mode": actual_industry_mode,
                    "include_tags": industry.get("include_tags") or [],
                    "exclude_tags": industry.get("exclude_tags") or [],
                },
            }

        if "attachment_requirement_text" in case:
            document_case_count += 1
            predicted_documents = {
                item["name"]
                for item in _extract_required_documents_from_attachment(
                    case["attachment_requirement_text"],
                    case["source"],
                )
            }
            expected_documents = set(case["expected_documents"])
            _update_counts(document_counts, predicted_documents, expected_documents)
            if predicted_documents != expected_documents:
                case_mismatch["required_documents"] = {
                    "expected": sorted(expected_documents),
                    "actual": sorted(predicted_documents),
                }

        if len(case_mismatch) > 2:
            mismatches.append(case_mismatch)

    case_count = len(cases)
    return {
        "fixture": str(path),
        "cases": case_count,
        "actual_policy_cases": sum(bool(case.get("source_pk")) for case in cases),
        "region": {
            "mode_accuracy": _ratio(region_mode_correct, case_count),
            **_metrics(region_counts),
        },
        "industry": {
            "mode_accuracy": _ratio(industry_mode_correct, case_count),
            **_metrics(industry_counts),
        },
        "required_documents": {
            "cases": document_case_count,
            **_metrics(document_counts),
        },
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _empty_counts() -> dict[str, int]:
    return {"tp": 0, "fp": 0, "fn": 0}


def _update_counts(counts: dict[str, int], predicted: set[str], expected: set[str]) -> None:
    counts["tp"] += len(predicted & expected)
    counts["fp"] += len(predicted - expected)
    counts["fn"] += len(expected - predicted)


def _metrics(counts: dict[str, int]) -> dict[str, float | int]:
    precision = _ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = _ratio(counts["tp"], counts["tp"] + counts["fn"])
    f1 = _ratio(2 * precision * recall, precision + recall)
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def main() -> None:
    print(
        json.dumps(
            evaluate_normalization_quality(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
