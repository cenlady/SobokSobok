from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rag_utils import OllamaEmbeddingModel, OpenAIEmbeddingModel
from app.models.normalized_policy import NormalizedPolicy
from app.models.recommend import RecommendationVector
from app.schemas.recommend import NumberRangeInput, RecommendationProfileRequest, RecommendationResult


VECTOR_TYPE_POLICY_RECOMMENDATION = "policy_recommendation"

INDUSTRY_LABELS = {
    "restaurant": "음식점업",
    "manufacturing": "제조업",
    "retail": "도소매업",
    "tourism": "관광/숙박업",
    "market": "전통시장/상점가",
    "export": "수출/해외진출",
    "digital": "디지털/온라인",
    "agriculture_fishery_forestry": "농림수산업",
    "information_communication": "정보통신업",
    "other_business": "기타 업종",
    "company_other_business": "기타 기업",
}

BUSINESS_STATUS_LABELS = {
    "small_business": "소상공인",
    "operating_business": "운영 중 사업자",
    "pre_founder": "예비창업자",
    "closing_business": "폐업/재기 준비 사업자",
    "small_manufacturer": "소공인",
    "traditional_market": "전통시장/상점가",
    "small_medium_business": "중소기업",
}

NEED_TAG_KEYWORDS = {
    "funding": ("현금", "융자", "대출", "자금", "보조금", "지원금", "감면", "보험료", "장려금", "수수료", "바우처"),
    "education_consulting": ("교육", "역량강화", "아카데미", "강의", "훈련", "상담", "컨설팅", "멘토링", "코칭", "전문가", "자문"),
    "digital": ("디지털", "스마트", "온라인", "플랫폼", "키오스크", "인공지능", "정보통신", "소프트웨어", "전자상거래", "라이브커머스"),
    "marketing": ("판로", "마케팅", "홍보", "전시", "박람회", "수출", "해외", "입점", "판매", "온누리상품권", "상품권"),
    "facility": ("시설", "장비", "환경개선", "점포개선", "냉난방기", "기계", "설비", "현물", "시설이용"),
    "recovery": ("재기", "폐업", "희망리턴", "재창업", "전직", "피해회복"),
    "employment": ("고용", "일자리", "인건비", "근로자", "채용", "인력", "노무"),
}

NEED_TAG_LABELS = {
    "funding": "자금",
    "education_consulting": "교육/컨설팅",
    "digital": "디지털/온라인",
    "marketing": "판로/마케팅",
    "facility": "시설/장비",
    "recovery": "재기/폐업지원",
    "employment": "고용/인력",
}


@dataclass
class MatchEvaluation:
    status: str = "eligible"
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    unknown_conditions: list[str] = field(default_factory=list)
    soft_mismatches: list[str] = field(default_factory=list)
    matched_tags: dict[str, list[str]] = field(default_factory=dict)


MATCH_STATUS_PRIORITY = {
    "eligible": 0,
    "needs_review": 1,
    "near_match": 2,
    "ineligible": 3,
}


def recommend_policies(
    db: Session,
    profile: RecommendationProfileRequest,
    limit: int = 15,
) -> tuple[list[RecommendationResult], bool, int]:
    policies = _candidate_query(db).all()
    vector_scores, vector_used = _vector_scores(db, profile) if profile.use_vectors else ({}, False)

    deduplicated: dict[str, RecommendationResult] = {}
    for policy in policies:
        evaluation = evaluate_policy(policy, profile)
        if evaluation.status == "ineligible":
            continue

        vector_similarity = vector_scores.get(policy.id)
        rank_score, score_breakdown = _rank_policy(policy, evaluation, profile, vector_similarity)
        result = RecommendationResult(
            policy_id=policy.id,
            title=policy.title,
            summary=policy.summary,
            organization=policy.organization,
            support_type=policy.support_type,
            support_content=policy.support_content,
            apply_url=policy.apply_url,
            apply_end=policy.apply_end,
            match_status=evaluation.status,
            confidence=_confidence(evaluation),
            rank_score=round(rank_score, 3),
            vector_similarity=round(vector_similarity, 4) if vector_similarity is not None else None,
            score_breakdown=score_breakdown,
            reasons=evaluation.reasons[:6],
            warnings=evaluation.warnings[:4],
            unknown_conditions=evaluation.unknown_conditions,
            unmet_conditions=evaluation.soft_mismatches,
            matched_tags=evaluation.matched_tags,
        )

        duplicate_key = policy.duplicate_group_key or f"{policy.source}:{policy.source_pk}"
        current = deduplicated.get(duplicate_key)
        if current is None or _result_sort_key(result) < _result_sort_key(current):
            deduplicated[duplicate_key] = result

    results = sorted(deduplicated.values(), key=_result_sort_key)
    return results[:limit], vector_used, len(results)


def evaluate_policy(policy: NormalizedPolicy, profile: RecommendationProfileRequest) -> MatchEvaluation:
    evaluation = MatchEvaluation()
    _check_region(policy, profile, evaluation)
    _check_business_status(policy, profile, evaluation)
    _check_employee_limit(policy, profile, evaluation)
    _check_sales_limit(policy, profile, evaluation)
    _check_business_age_limit(policy, profile, evaluation)
    _check_industry(policy, profile, evaluation)
    _check_need_tags(policy, profile, evaluation)
    _check_apply_status(policy, evaluation)

    if evaluation.failed:
        evaluation.status = "ineligible"
    elif evaluation.soft_mismatches:
        evaluation.status = "near_match"
    elif evaluation.warnings:
        evaluation.status = "needs_review"
    else:
        evaluation.status = "eligible"

    return evaluation


def explain_policy_recommendation(
    db: Session,
    policy_id: UUID,
    profile: RecommendationProfileRequest,
) -> RecommendationExplanationResponse:
    from app.schemas.recommend import RecommendationExplanationResponse
    policy = db.get(NormalizedPolicy, policy_id)
    if not policy:
        raise ValueError("Policy not found")

    evaluation = evaluate_policy(policy, profile)

    fallback_summary = "지원 조건 충족률이 높습니다." if evaluation.status == "eligible" else "지원 조건 확인이 필요합니다."
    fallback_strengths = evaluation.reasons
    fallback_aspects_to_check = evaluation.failed + evaluation.soft_mismatches + evaluation.warnings
    
    fallback_next_actions = []
    if policy.apply_end:
        days_left = (policy.apply_end - datetime.now()).days
        if days_left >= 0:
            fallback_next_actions.append(f"마감일({policy.apply_end.strftime('%m월 %d일')})이 {days_left}일 남았으니 늦지 않게 신청해 보세요.")
        else:
            fallback_next_actions.append("신청 기간이 마감되었는지 확인해 보세요.")
    else:
        fallback_next_actions.append("신청 기간을 확인해 보세요.")
    fallback_next_actions.append("우측 하단의 'AI 상담' 버튼을 눌러 상세 지원 서류와 자격을 물어보세요.")

    fallback_response = RecommendationExplanationResponse(
        summary=fallback_summary,
        strengths=fallback_strengths,
        aspects_to_check=fallback_aspects_to_check,
        next_actions=fallback_next_actions
    )

    if not settings.GEMINI_API_KEY:
        return fallback_response

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        profile_region = f"{profile.region.sido or ''} {profile.region.sigungu or ''}".strip() or "전국"
        profile_industries = _labels(profile.industry_tags, INDUSTRY_LABELS) or "전체"
        profile_statuses = _labels(profile.business_status_tags, BUSINESS_STATUS_LABELS) or "전체"
        profile_employees = _range_text(profile.employees, "명") or "제한 없음"
        profile_sales = _money_range_text(profile.annual_sales_krw) or "제한 없음"
        profile_age = _range_text(profile.business_age_years, "년") or "제한 없음"
        profile_needs = _labels(profile.need_tags, NEED_TAG_LABELS) or "제한 없음"
        
        policy_title = policy.title or ""
        policy_summary = policy.summary or ""
        policy_target = policy.target_text or ""
        policy_support = policy.support_content or ""
        policy_apply_period = f"{policy.apply_start.strftime('%Y-%m-%d') if policy.apply_start else '시작일 미정'} ~ {policy.apply_end.strftime('%Y-%m-%d') if policy.apply_end else '마감일 미정'}"
        
        prompt = f"""당신은 소상공인에게 맞춤형 정책을 설명해주는 친절한 AI 상담사 '소복이'입니다.
지원 정책의 정보와 사용자의 프로필, 그리고 규칙 기반으로 분석한 적합성 평가 결과를 바탕으로 사용자에게 최적화된 맞춤형 추천 근거를 자연스럽고 친절하게 작성해 주세요.

[사용자 프로필]
- 지역: {profile_region}
- 업종: {profile_industries}
- 사업자 상태: {profile_statuses}
- 직원수: {profile_employees}
- 연매출: {profile_sales}
- 업력: {profile_age}
- 관심 분야: {profile_needs}

[지원 정책 정보]
- 정책명: {policy_title}
- 정책 요약: {policy_summary}
- 지원 대상: {policy_target}
- 지원 내용: {policy_support}
- 접수 기간: {policy_apply_period}

[적합성 평가 결과]
- 판정 상태: {evaluation.status}
- 잘 맞는 조건 (reasons): {evaluation.reasons}
- 불확실하거나 주의할 조건 (warnings): {evaluation.warnings}
- 충족하지 못한 조건 (failed): {evaluation.failed}

위의 정보들을 종합하여 다음 네 가지 항목을 포함하는 JSON 객체를 반환해 주세요.

1. AI 추천 이유 (한 줄 요약) ("summary"): 사용자의 어떤 조건이 이 정책과 완벽히 부합하며 왜 추천하는지, 친근한 대화체(ex: "~해서 추천해 드려요!")로 1줄로 요약해 주세요.
2. 잘 맞는 부분 ("strengths"): 규칙 평가 결과(reasons)와 지원 대상을 연관 지어 사용자와 잘 맞는 부분을 구체적이고 읽기 쉬운 항목으로 작성해 주세요. (2~4개 권장, ex: "- 서울 마포구 소상공인을 대상으로 하여 조건에 잘 맞아요.")
3. 확인할 부분 ("aspects_to_check"): 규칙 평가 결과(warnings/failed)를 바탕으로 사용자가 지원하기 전에 세부적으로 확인해야 하거나 모호한 점을 구체적이고 읽기 쉬운 항목으로 작성해 주세요. (1~3개 권장, ex: "- 공고에 구체적인 업종 제한이 없어 세부 확인이 필요해요.")
4. 다음 행동 ("next_actions"): 신청 기한(apply_end), AI 상담 활용법 등을 포함하여 사용자가 바로 취해야 할 구체적인 행동을 항목으로 제안해 주세요. (1~3개 권장, ex: "- 마감일(7월 20일)까지 10일 남았으니 서류를 미리 준비해 보세요.", "- AI 상담을 통해 필요한 서류가 무엇인지 질문해 보세요.")

출력 형식은 반드시 아래 JSON 스키마를 만족해야 하며, 마크다운 코드 블록 없이 순수한 JSON 문자열로만 응답해 주세요.
{{
  "summary": "한 줄 요약 스트링",
  "strengths": ["잘 맞는 부분 1", "잘 맞는 부분 2"],
  "aspects_to_check": ["확인할 부분 1", "확인할 부분 2"],
  "next_actions": ["다음 행동 1", "다음 행동 2"]
}}"""

        response = client.models.generate_content(
            model=settings.GEMINI_TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        res_text = response.text.strip()
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        elif res_text.startswith("```"):
            res_text = res_text[3:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
        res_text = res_text.strip()
        
        data = json.loads(res_text)
        return RecommendationExplanationResponse(
            summary=data.get("summary", fallback_summary),
            strengths=data.get("strengths", fallback_strengths),
            aspects_to_check=data.get("aspects_to_check", fallback_aspects_to_check),
            next_actions=data.get("next_actions", fallback_next_actions),
        )
    except Exception as e:
        print("Gemini API call failed, falling back:", str(e))
        return fallback_response


def build_recommendation_text(policy: NormalizedPolicy) -> str:
    eligibility = policy.eligibility or {}
    lines = [
        ("정책명", policy.title),
        ("요약", _clip(policy.summary, 300)),
        ("지원대상", _clip(policy.target_text, 500)),
        ("지원내용", _clip(policy.support_content, 800)),
        ("지원유형", policy.support_type),
        ("지역조건", _region_text(policy)),
        ("업종조건", _labels(policy.industry_tags or [], INDUSTRY_LABELS)),
        ("사업자상태조건", _labels(policy.business_status_tags or [], BUSINESS_STATUS_LABELS)),
        ("직원수조건", _source_text(eligibility, "employee_limit")),
        ("매출조건", _source_text(eligibility, "sales_limit")),
        ("업력조건", _source_text(eligibility, "business_age_limit")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in lines if value)


def build_recommendation_metadata(policy: NormalizedPolicy) -> dict[str, Any]:
    return {
        "policy_id": str(policy.id),
        "source": policy.source,
        "source_pk": policy.source_pk,
        "vector_type": VECTOR_TYPE_POLICY_RECOMMENDATION,
        "region_scope": policy.region_scope,
        "sido": policy.sido,
        "sigungu": policy.sigungu,
        "matched_sidos": policy.matched_sidos or [],
        "industry_tags": policy.industry_tags or [],
        "business_status_tags": policy.business_status_tags or [],
        "support_type": policy.support_type,
        "status": policy.status,
        "apply_end": policy.apply_end.isoformat() if policy.apply_end else None,
    }


def build_profile_query(profile: RecommendationProfileRequest) -> str:
    region = profile.region
    region_text = " ".join(part for part in [region.sido if region else None, region.sigungu if region else None] if part)
    industries = _labels(profile.industry_tags, INDUSTRY_LABELS) or "업종 미입력"
    statuses = _labels(profile.business_status_tags, BUSINESS_STATUS_LABELS) or "사업자 상태 미입력"
    employees = _range_text(profile.employees, "명")
    sales = _money_range_text(profile.annual_sales_krw)
    age = _range_text(profile.business_age_years, "년")
    needs = _labels(profile.need_tags, NEED_TAG_LABELS)

    lines = [
        f"{region_text or '지역 미입력'}에서 {industries}을 운영하거나 준비하는 {statuses}입니다.",
        f"직원수는 {employees or '미입력'}, 연매출은 {sales or '미입력'}, 업력은 {age or '미입력'}입니다.",
    ]
    if needs:
        lines.append(f"원하는 지원은 {needs}입니다.")
    return " ".join(lines)


def source_hash(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def fit_embedding_dim(vector: list[float], dim: int | None = None) -> list[float]:
    target_dim = dim or settings.REC_EMBEDDING_DIM
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - len(vector))


def _candidate_query(db: Session):
    now = datetime.now()
    return (
        db.query(NormalizedPolicy)
        .filter(NormalizedPolicy.is_active.is_(True))
        .filter((NormalizedPolicy.status.is_(None)) | (NormalizedPolicy.status != "closed"))
        .filter((NormalizedPolicy.apply_end.is_(None)) | (NormalizedPolicy.apply_end >= now))
    )


def _vector_scores(db: Session, profile: RecommendationProfileRequest) -> tuple[dict[UUID, float], bool]:
    vector_count = (
        db.query(RecommendationVector)
        .filter(RecommendationVector.vector_type == VECTOR_TYPE_POLICY_RECOMMENDATION)
        .filter(RecommendationVector.embedding_status == "success")
        .filter(RecommendationVector.embedding.isnot(None))
        .count()
    )
    if vector_count == 0:
        return {}, False

    try:
        model = _embedding_model()
        query_vector = fit_embedding_dim(model.embed_text(build_profile_query(profile)))
        distance = RecommendationVector.embedding.cosine_distance(query_vector)
        rows = (
            db.query(RecommendationVector.policy_id, (1 - distance).label("similarity"))
            .filter(RecommendationVector.vector_type == VECTOR_TYPE_POLICY_RECOMMENDATION)
            .filter(RecommendationVector.embedding_status == "success")
            .filter(RecommendationVector.embedding.isnot(None))
            .order_by(distance)
            .limit(250)
            .all()
        )
        return {policy_id: float(similarity) for policy_id, similarity in rows}, True
    except Exception:
        return {}, False


def _embedding_model():
    if settings.REC_EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingModel(model_name=settings.REC_OPENAI_MODEL)
    return OllamaEmbeddingModel(
        model_name=settings.REC_OLLAMA_MODEL,
        base_url=settings.REC_OLLAMA_BASE_URL,
    )


def _check_region(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    user_sido = profile.region.sido if profile.region else None
    user_sigungu = profile.region.sigungu if profile.region else None
    matched_sidos = set(policy.matched_sidos or [])
    if policy.region_scope == "national":
        evaluation.reasons.append("전국 신청 가능 정책입니다.")
        return
    if policy.region_scope == "unknown":
        evaluation.warnings.append("공고의 지역 조건이 명확하지 않습니다.")
        evaluation.unknown_conditions.append("지역")
        return
    if not user_sido:
        evaluation.warnings.append("사용자 지역이 없어 지역 조건 확인이 필요합니다.")
        evaluation.unknown_conditions.append("사용자 지역")
        return

    if not matched_sidos and not policy.sido:
        evaluation.warnings.append("지역 정책이지만 대상 시·도를 확인할 수 없습니다.")
        evaluation.unknown_conditions.append("정책 대상 지역")
        return

    if user_sido not in matched_sidos and user_sido != policy.sido:
        evaluation.failed.append("지역 조건이 맞지 않습니다.")
        return

    if policy.sigungu:
        if not user_sigungu:
            evaluation.warnings.append(f"{policy.sigungu} 대상 정책으로 시·군·구 확인이 필요합니다.")
            evaluation.unknown_conditions.append("시·군·구")
            return
        if user_sigungu != policy.sigungu:
            evaluation.failed.append(f"{policy.sigungu} 대상 정책으로 사용자 지역과 맞지 않습니다.")
            return
        evaluation.reasons.append(f"{user_sido} {user_sigungu}에서 신청 가능한 정책입니다.")
        evaluation.matched_tags["region"] = [user_sido, user_sigungu]
        return

    evaluation.reasons.append(f"{user_sido} 지역에서 신청 가능한 정책입니다.")
    evaluation.matched_tags["region"] = [user_sido]


def _check_business_status(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    policy_tags = set(policy.business_status_tags or [])
    user_tags = set(profile.business_status_tags or [])
    if not policy_tags:
        evaluation.warnings.append("공고의 사업자 상태 조건이 명확하지 않습니다.")
        evaluation.unknown_conditions.append("사업자 상태")
        return
    if not user_tags:
        evaluation.warnings.append("사용자 사업자 상태가 없어 대상 조건 확인이 필요합니다.")
        evaluation.unknown_conditions.append("사용자 사업자 상태")
        return

    operating_tags = {"operating_business", "pre_founder", "closing_business"}
    scale_tags = {"small_business", "small_medium_business"}
    special_tags = {"small_manufacturer", "traditional_market"}
    policy_operating = policy_tags & operating_tags
    user_operating = user_tags & operating_tags
    policy_scale = policy_tags & scale_tags
    user_scale = user_tags & scale_tags
    policy_special = policy_tags & special_tags
    user_special = user_tags & special_tags

    if policy_operating and user_operating and not (policy_operating & user_operating) and not (policy_scale & user_scale):
        evaluation.failed.append("사업 운영 상태 조건이 맞지 않습니다.")
        return

    if policy_scale and not (policy_scale & user_scale):
        if policy_scale == {"small_medium_business"} and "small_business" in user_tags:
            evaluation.soft_mismatches.append("중소기업 대상 정책으로 소상공인 신청 가능 범위를 확인해야 합니다.")
            return
        evaluation.failed.append("사업자 규모 조건이 맞지 않습니다.")
        return

    if policy_special and not (policy_special & user_special):
        evaluation.soft_mismatches.append("소공인·전통시장 등 특수 대상 여부를 추가로 확인해야 합니다.")
        return

    matched = sorted(policy_tags & user_tags)
    if matched:
        evaluation.reasons.append(f"사업자 상태가 맞습니다: {_labels(matched, BUSINESS_STATUS_LABELS)}")
        evaluation.matched_tags["business_status_tags"] = matched
        return

    evaluation.failed.append("사업자 대상 조건이 맞지 않습니다.")


def _check_industry(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    policy_tags = set(policy.industry_tags or [])
    user_tags = set(profile.industry_tags or [])
    if not policy_tags:
        evaluation.warnings.append("공고의 업종 조건이 명확하지 않습니다.")
        evaluation.unknown_conditions.append("업종")
        return
    if not user_tags:
        evaluation.warnings.append("사용자 업종이 없어 업종 적합도 확인이 필요합니다.")
        evaluation.unknown_conditions.append("사용자 업종")
        return

    matched = sorted(policy_tags & user_tags)
    if matched:
        evaluation.reasons.append(f"업종과 관련된 정책입니다: {_labels(matched, INDUSTRY_LABELS)}")
        evaluation.matched_tags["industry_tags"] = matched
    else:
        evaluation.soft_mismatches.append("업종 태그가 직접 일치하지 않는 유사 정책입니다.")


def _check_employee_limit(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    _check_numeric_limit(
        label="직원수",
        unit="명",
        user_value=profile.employees,
        constraints=_numeric_constraints(
            policy,
            eligibility_key="employee_limit",
            flat_operator=policy.employee_limit_operator,
            flat_value=policy.employee_limit_value,
        ),
        evaluation=evaluation,
    )


def _check_sales_limit(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    _check_numeric_limit(
        label="연매출",
        unit="원",
        user_value=profile.annual_sales_krw,
        constraints=_numeric_constraints(
            policy,
            eligibility_key="sales_limit",
            flat_operator=policy.sales_limit_operator,
            flat_value=policy.sales_limit_amount_krw,
        ),
        evaluation=evaluation,
    )


def _check_business_age_limit(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    _check_numeric_limit(
        label="업력",
        unit="년",
        user_value=profile.business_age_years,
        constraints=_numeric_constraints(
            policy,
            eligibility_key="business_age_limit",
            flat_operator=policy.business_age_limit_operator,
            flat_value=policy.business_age_limit_value,
        ),
        evaluation=evaluation,
    )


def _check_numeric_limit(
    label: str,
    unit: str,
    user_value: NumberRangeInput | int | None,
    constraints: list[tuple[str, int]],
    evaluation: MatchEvaluation,
) -> None:
    if not constraints:
        return
    if user_value is None:
        evaluation.warnings.append(f"{label} 입력 정보가 없어 추가 확인이 필요합니다.")
        evaluation.unknown_conditions.append(label)
        return

    limit_operator_korean = {
        "<=": "이하",
        "<": "미만",
        ">=": "이상",
        ">": "초과"
    }

    matched_texts: list[str] = []
    uncertain_texts: list[str] = []
    for operator, limit_value in constraints:
        operator_text = limit_operator_korean.get(operator, operator)
        limit_text = f"{label} {limit_value:,}{unit} {operator_text}"
        result = _compare_user_range(user_value, operator, limit_value)
        if result is False:
            evaluation.failed.append(f"{limit_text} 기준에 맞지 않습니다.")
            return
        if result is None:
            uncertain_texts.append(limit_text)
        else:
            matched_texts.append(limit_text)

    if uncertain_texts:
        evaluation.warnings.append(f"공고상의 {' · '.join(uncertain_texts)} 조건과 입력 범위가 일부만 겹칩니다.")
        evaluation.unknown_conditions.append(label)
        return
    if matched_texts:
        evaluation.reasons.append(f"{' · '.join(matched_texts)} 기준에 부합합니다.")


def _check_need_tags(policy: NormalizedPolicy, profile: RecommendationProfileRequest, evaluation: MatchEvaluation) -> None:
    if not profile.need_tags:
        return
    policy_need_tags = set(classify_need_tags(policy))
    matched = sorted(policy_need_tags & set(profile.need_tags))
    if matched:
        evaluation.reasons.append(f"원하는 지원 유형과 맞습니다: {_labels(matched, NEED_TAG_LABELS)}")
        evaluation.matched_tags["need_tags"] = matched


def _check_apply_status(policy: NormalizedPolicy, evaluation: MatchEvaluation) -> None:
    now = datetime.now()
    if policy.status == "closed" or (policy.apply_end and policy.apply_end < now):
        evaluation.failed.append("신청 기간이 종료된 정책입니다.")
        return
    if policy.apply_start and policy.apply_start > now:
        evaluation.soft_mismatches.append(
            f"{policy.apply_start.strftime('%Y-%m-%d')}부터 신청 가능한 예정 정책입니다."
        )
        return

    if policy.status == "open":
        evaluation.reasons.append("현재 접수 가능 상태입니다.")
    elif policy.status == "notice":
        evaluation.warnings.append("안내/공고 상태라 실제 신청 가능 여부 확인이 필요합니다.")
        evaluation.unknown_conditions.append("신청 가능 상태")
    elif not policy.status:
        evaluation.warnings.append("현재 신청 가능 상태가 명확하지 않습니다.")
        evaluation.unknown_conditions.append("신청 가능 상태")

    if policy.apply_end:
        days_left = (policy.apply_end - now).days
        if 0 <= days_left <= 14:
            evaluation.reasons.append(f"마감까지 {days_left}일 남았습니다.")


def classify_need_tags(policy: NormalizedPolicy) -> list[str]:
    text = " ".join(
        value
        for value in [
            policy.title,
            policy.summary,
            policy.support_type,
            policy.support_content,
        ]
        if value
    )
    return [
        tag
        for tag, keywords in NEED_TAG_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]


def _rank_policy(
    policy: NormalizedPolicy,
    evaluation: MatchEvaluation,
    profile: RecommendationProfileRequest,
    vector_similarity: float | None,
) -> tuple[float, dict[str, float]]:
    policy_need_tags = set(classify_need_tags(policy))
    requested_need_tags = set(profile.need_tags)
    if not requested_need_tags:
        need_match = 20.0
    else:
        need_match = 35.0 * len(policy_need_tags & requested_need_tags) / len(requested_need_tags)

    policy_industries = set(policy.industry_tags or [])
    user_industries = set(profile.industry_tags or [])
    if policy_industries and user_industries and policy_industries & user_industries:
        industry_relevance = 20.0
    elif not policy_industries:
        industry_relevance = 12.0
    else:
        industry_relevance = 2.0

    now = datetime.now()
    if policy.apply_start and policy.apply_start > now:
        actionability = 4.0
    elif policy.status == "open":
        actionability = 15.0
    elif policy.status == "notice":
        actionability = 7.0
    else:
        actionability = 5.0
    if policy.apply_end:
        days_left = (policy.apply_end - now).days
        if 0 <= days_left <= 30:
            actionability += 5.0
        elif days_left > 30:
            actionability += 3.0

    data_quality = max(
        2.0,
        15.0 - (3.0 * len(evaluation.unknown_conditions)) - (2.0 * len(evaluation.soft_mismatches)),
    )
    semantic = 5.0 if vector_similarity is None else max(0.0, min(vector_similarity, 1.0)) * 10.0

    breakdown = {
        "need_match": round(need_match, 3),
        "industry_relevance": round(industry_relevance, 3),
        "actionability": round(min(actionability, 20.0), 3),
        "data_quality": round(data_quality, 3),
        "semantic_similarity": round(semantic, 3),
    }
    return min(sum(breakdown.values()), 100.0), breakdown


def _confidence(evaluation: MatchEvaluation) -> str:
    if evaluation.status == "eligible":
        return "high"
    if evaluation.status == "needs_review" and len(evaluation.unknown_conditions) <= 2:
        return "medium"
    return "low"


def _result_sort_key(item: RecommendationResult) -> tuple[int, float]:
    return MATCH_STATUS_PRIORITY[item.match_status], -item.rank_score


def _compare_user_range(
    value: NumberRangeInput | int,
    operator: str,
    limit_value: int,
) -> bool | None:
    lower, upper = _range_bounds(value)
    if operator == "<=":
        if upper is not None and upper <= limit_value:
            return True
        if lower is not None and lower > limit_value:
            return False
        return None
    if operator == "<":
        if upper is not None and upper < limit_value:
            return True
        if lower is not None and lower >= limit_value:
            return False
        return None
    if operator == ">=":
        if lower is not None and lower >= limit_value:
            return True
        if upper is not None and upper < limit_value:
            return False
        return None
    if operator == ">":
        if lower is not None and lower > limit_value:
            return True
        if upper is not None and upper <= limit_value:
            return False
        return None
    return None


def _numeric_constraints(
    policy: NormalizedPolicy,
    *,
    eligibility_key: str,
    flat_operator: str | None,
    flat_value: int | None,
) -> list[tuple[str, int]]:
    eligibility = policy.eligibility or {}
    raw = eligibility.get(eligibility_key)
    constraints: list[tuple[str, int]] = []
    if isinstance(raw, dict):
        min_value = raw.get("min_amount_krw", raw.get("min_value"))
        max_value = raw.get("max_amount_krw", raw.get("max_value"))
        min_operator = raw.get("min_operator")
        max_operator = raw.get("max_operator")
        parsed_min = _coerce_int(min_value)
        parsed_max = _coerce_int(max_value)
        if parsed_min is not None and min_operator in {">", ">="}:
            constraints.append((min_operator, parsed_min))
        if parsed_max is not None and max_operator in {"<", "<="}:
            constraints.append((max_operator, parsed_max))

    if not constraints and flat_value is not None and flat_operator in {"<", "<=", ">", ">="}:
        constraints.append((flat_operator, int(flat_value)))
    return constraints


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _range_bounds(value: NumberRangeInput | int | None) -> tuple[int | None, int | None]:
    if value is None:
        return None, None
    if isinstance(value, int):
        return value, value
    return value.min, value.max


def _range_text(value: NumberRangeInput | int | None, unit: str) -> str | None:
    lower, upper = _range_bounds(value)
    if lower is None and upper is None:
        return None
    if lower == upper:
        return f"{lower:,}{unit}"
    if lower is None:
        return f"{upper:,}{unit} 이하"
    if upper is None:
        return f"{lower:,}{unit} 이상"
    return f"{lower:,}~{upper:,}{unit}"


def _money_range_text(value: NumberRangeInput | int | None) -> str | None:
    lower, upper = _range_bounds(value)
    if lower is None and upper is None:
        return None
    if lower == upper:
        return _money_text(lower)
    if lower is None:
        return f"{_money_text(upper)} 이하"
    if upper is None:
        return f"{_money_text(lower)} 이상"
    return f"{_money_text(lower)}~{_money_text(upper)}"


def _money_text(value: int) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:g}억원"
    if value >= 10_000:
        return f"{value / 10_000:g}만원"
    return f"{value:,}원"


def _labels(tags: list[str] | set[str], label_map: dict[str, str]) -> str:
    return ", ".join(label_map.get(tag, tag) for tag in tags)


def _region_text(policy: NormalizedPolicy) -> str:
    if policy.region_scope == "national":
        return "전국"
    if policy.matched_sidos:
        return ", ".join(policy.matched_sidos)
    return " ".join(part for part in [policy.sido, policy.sigungu] if part) or "명시 없음"


def _source_text(eligibility: dict[str, Any], key: str) -> str | None:
    value = eligibility.get(key)
    if isinstance(value, dict):
        return value.get("source_text")
    return None


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
