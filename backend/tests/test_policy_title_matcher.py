import uuid
from datetime import datetime

from app.services.policy_title_matcher import (
    PolicyTitleEntry,
    build_policy_title_forms,
    normalize_policy_title,
    resolve_policy_title,
)


def _entry(title: str, *, group: str | None = None, status: str = "open") -> PolicyTitleEntry:
    return PolicyTitleEntry(
        policy_id=uuid.uuid4(),
        title=title,
        duplicate_group_key=group or str(uuid.uuid4()),
        summary=None,
        support_type=None,
        apply_end=None,
        status=status,
        updated_at=datetime(2026, 7, 16),
        forms=build_policy_title_forms(title),
    )


def test_normalize_policy_title_ignores_spacing_and_punctuation():
    assert normalize_policy_title("[2026년] 소상공인 정책자금!") == "2026년소상공인정책자금"


def test_short_official_title_beats_long_title_core_alias():
    long_policy = _entry("2026년 소상공인 정책자금 융자계획 공고(수정)")
    short_policy = _entry("소상공인정책자금")

    result = resolve_policy_title(
        "소상공인 정책자금 신청 기간 알려줘",
        (long_policy, short_policy),
    )

    assert result.status == "matched"
    assert result.policy_id == short_policy.policy_id
    assert result.match_type == "full"


def test_long_admin_clean_title_beats_its_short_substring():
    long_policy = _entry("2026년 소상공인 정책자금 융자계획 공고(수정)")
    short_policy = _entry("소상공인정책자금")

    result = resolve_policy_title(
        "2026년 소상공인 정책자금 융자계획 공고 신청 기간 알려줘",
        (long_policy, short_policy),
    )

    assert result.status == "matched"
    assert result.policy_id == long_policy.policy_id
    assert result.match_type == "admin_clean"


def test_same_core_alias_for_different_policies_requires_selection():
    first = _entry("소상공인 정책자금 융자계획 공고")
    second = _entry("소상공인 정책자금 지원사업")

    result = resolve_policy_title(
        "소상공인 정책자금 신청 기간 알려줘",
        (first, second),
    )

    assert result.status == "ambiguous"
    assert {candidate["policy_id"] for candidate in result.candidates} == {
        str(first.policy_id),
        str(second.policy_id),
    }


def test_generic_query_does_not_auto_select_policy():
    policy = _entry("소상공인 지원사업")

    result = resolve_policy_title("지원사업 신청 기간 알려줘", (policy,))

    assert result.status == "none"
