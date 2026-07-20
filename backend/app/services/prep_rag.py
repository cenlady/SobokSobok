from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.model_provider import get_embedding_model, normalize_model_mode
from app.core.rag_utils import search_generic_vectors
from app.models.prep import PrepVector
from app.services.document_guides import GUIDE_BY_NAME, DocumentGuide
from app.services.document_names import (
    find_canonical_name_matches_in_text,
    find_canonical_names_in_text,
)


DOCUMENT_GUIDE_ACTIONS = (
    "설명",
    "알려",
    "뭐야",
    "무엇",
    "어떤 문서",
    "어디서",
    "발급",
    "떼는",
    "떼야",
    "작성",
    "쓰는",
    "써야",
    "준비",
    "제출",
    "내는",
    "필요",
    "방법",
    "양식",
    "수수료",
    "비용",
    "얼마나 걸",
)

DOCUMENT_GUIDE_MARKERS = (
    "문서",
    "서류",
    "계획서",
    "신청서",
    "증명서",
    "증명원",
    "확인서",
    "동의서",
    "신고서",
    "등본",
    "초본",
    "등록증",
    "사본",
)

POLICY_SEARCH_ACTIONS = (
    "추천",
    "찾아",
    "검색",
    "알려줘",
    "알려 줘",
    "어떤 게",
    "어떤게",
    "있어",
)
POLICY_SEARCH_TARGETS = ("정책", "공고", "지원사업", "지원 사업", "복지")
PREP_VECTOR_MIN_SIMILARITY = 0.45


@dataclass(frozen=True)
class DocumentGuideMatch:
    document_name: str
    display_name: str
    guide_text: str
    similarity: float
    exact: bool
    guide: DocumentGuide | None = None


@dataclass(frozen=True)
class DocumentGuideResolution:
    document_names: tuple[str, ...]
    answer: str
    exact: bool


def prep_vector_column_for_mode(model_mode: str | None) -> tuple[str, Any]:
    selected_mode = normalize_model_mode(model_mode) or "local"
    column = (
        PrepVector.embedding_openai
        if selected_mode == "cloud"
        else PrepVector.embedding_ollama
    )
    return selected_mode, column


def search_prep_guides(
    db: Session,
    query: str,
    *,
    model_mode: str | None,
    limit: int = 5,
) -> list[tuple[PrepVector, float]]:
    normalized_query = query.strip()
    if not normalized_query or limit <= 0:
        return []

    selected_mode, vector_column = prep_vector_column_for_mode(model_mode)
    available = (
        db.query(func.count(PrepVector.id))
        .filter(vector_column.isnot(None))
        .scalar()
        or 0
    )
    if available == 0:
        return []

    embedder = get_embedding_model("prep", model_mode=selected_mode)
    return search_generic_vectors(
        db=db,
        model_class=PrepVector,
        query=normalized_query,
        embedding_model=embedder,
        embedding_column=vector_column,
        limit=limit,
    )


def exact_document_guide_names(query: str) -> list[str]:
    """질문 안에서 수작업 검증된 발급 가이드의 서류명을 찾는다."""
    return find_canonical_names_in_text(
        query,
        allowed_names=GUIDE_BY_NAME.keys(),
    )


def is_document_guide_question(query: str) -> bool:
    """정책 검색이 아니라 특정 서류의 뜻·발급·작성 방법을 묻는지 판별한다."""
    normalized = re.sub(r"\s+", " ", (query or "").strip().lower())
    if not normalized:
        return False

    # "사업계획서가 필요한 지원사업 찾아줘"는 서류 설명이 아니라 정책 검색이다.
    if any(action in normalized for action in POLICY_SEARCH_ACTIONS) and any(
        target in normalized for target in POLICY_SEARCH_TARGETS
    ):
        return False

    exact_names = exact_document_guide_names(normalized)
    has_action = any(action in normalized for action in DOCUMENT_GUIDE_ACTIONS)
    if exact_names:
        # 서류명만 짧게 입력한 경우에도 해당 서류를 설명하는 요청으로 본다.
        compact_query = re.sub(r"[^0-9a-z가-힣]", "", normalized)
        compact_names = [re.sub(r"[^0-9a-z가-힣]", "", name.lower()) for name in exact_names]
        return has_action or any(
            compact_query == name or len(compact_query) <= len(name) + 5
            for name in compact_names
        )

    return has_action and any(marker in normalized for marker in DOCUMENT_GUIDE_MARKERS)


def find_document_guide_matches(
    db: Session,
    query: str,
    *,
    model_mode: str | None,
    limit: int = 3,
) -> list[DocumentGuideMatch]:
    """정확한 서류명은 직접 찾고, 표현이 다를 때만 prep_vectors를 검색한다."""
    exact_name_matches = find_canonical_name_matches_in_text(
        query,
        allowed_names=GUIDE_BY_NAME.keys(),
    )[:limit]
    if exact_name_matches:
        exact_names = [canonical for _display_name, canonical in exact_name_matches]
        display_names = {
            canonical: display_name
            for display_name, canonical in exact_name_matches
        }
        rows = (
            db.query(PrepVector)
            .filter(PrepVector.document_name.in_(exact_names))
            .all()
        )
        rows_by_name = {row.document_name: row for row in rows}
        matches: list[DocumentGuideMatch] = []
        for name in exact_names:
            guide = GUIDE_BY_NAME.get(name)
            row = rows_by_name.get(name)
            guide_text = str(getattr(row, "guide_text", "") or "").strip()
            if not guide_text and guide is not None:
                guide_text = guide.to_text()
            if not guide_text:
                continue
            matches.append(
                DocumentGuideMatch(
                    document_name=name,
                    display_name=display_names.get(name, name),
                    guide_text=guide_text,
                    similarity=1.0,
                    exact=True,
                    guide=guide,
                )
            )
        return matches

    if not is_document_guide_question(query):
        return []

    results = search_prep_guides(
        db,
        query,
        model_mode=model_mode,
        limit=max(limit, 1),
    )
    matches = []
    for row, similarity in results:
        if similarity < PREP_VECTOR_MIN_SIMILARITY or not row.guide_text:
            continue
        matches.append(
            DocumentGuideMatch(
                document_name=row.document_name,
                display_name=row.document_name,
                guide_text=row.guide_text,
                similarity=similarity,
                exact=False,
                guide=GUIDE_BY_NAME.get(row.document_name),
            )
        )
        # 자연어가 모호할 때 여러 서류를 단정하지 않고 가장 가까운 하나만 안내한다.
        break
    return matches


def resolve_document_guide_question(
    db: Session,
    query: str,
    *,
    model_mode: str | None,
) -> DocumentGuideResolution | None:
    """서류 질문이면 검증된 가이드만 사용해 이해하기 쉬운 답변을 만든다."""
    if not is_document_guide_question(query):
        return None

    matches = find_document_guide_matches(
        db,
        query,
        model_mode=model_mode,
    )
    if not matches:
        return None

    answer_blocks = [_format_document_guide(match) for match in matches]
    return DocumentGuideResolution(
        document_names=tuple(match.document_name for match in matches),
        answer="\n\n".join(answer_blocks),
        exact=all(match.exact for match in matches),
    )


def _format_document_guide(match: DocumentGuideMatch) -> str:
    guide = match.guide
    display_name = match.display_name or match.document_name
    if guide is None:
        prefix = (
            f"질문과 가장 가까운 서류는 '{display_name}'이에요. "
            "서류명이 맞는지 먼저 확인해 주세요."
        )
        details = [part.strip() for part in match.guide_text.split(" / ") if part.strip()]
        return "\n".join([prefix, *(f"• {detail}" for detail in details)])

    uncertainty_lines = []
    if not match.exact:
        uncertainty_lines.append(
            f"질문과 가장 가까운 서류는 '{display_name}'이에요. "
            "서류명이 맞는지 먼저 확인해 주세요."
        )

    if guide.preparation_type == "template":
        lines = [
            *uncertainty_lines,
            f"{display_name}{_topic_particle(display_name)} 기관에서 발급받는 서류가 아니라, "
            "해당 공고에서 제공하는 양식을 내려받아 직접 작성하는 서류예요.",
        ]
        if guide.online:
            lines.append(f"• 양식 받는 곳: {guide.online}")
        lines.append(f"• 준비 방법: 공고에 첨부된 양식을 그대로 작성해 주세요.")
    elif guide.preparation_type == "self_written":
        lines = [
            *uncertainty_lines,
            f"{display_name}{_topic_particle(display_name)} 기관에서 발급받는 서류가 아니라, "
            "신청자가 직접 작성하는 문서예요.",
        ]
        if guide.online:
            lines.append(f"• 준비 방법: {guide.online}")
    elif guide.preparation_type == "owned":
        lines = [
            *uncertainty_lines,
            f"{display_name}{_topic_particle(display_name)} 새로 발급받기보다 현재 가지고 있는 것을 준비하면 돼요.",
        ]
        if guide.offline:
            lines.append(f"• 준비 가능한 종류: {guide.offline}")
    else:
        lines = [
            *uncertainty_lines,
            f"{display_name}{_topic_particle(display_name)} {guide.issuer}에서 발급받는 서류예요.",
        ]
        if guide.online:
            lines.append(f"• 온라인: {guide.online}")
        if guide.offline:
            lines.append(f"• 방문: {guide.offline}")

    duration_label = "준비 시간" if guide.preparation_type in {"template", "self_written", "owned"} else "예상 시간"
    lines.append(f"• {duration_label}: {guide.duration}")
    lines.append(f"• 비용: {guide.fee}")
    if guide.tip:
        lines.append(f"• 꼭 확인할 점: {guide.tip}")
    return "\n".join(lines)


def _topic_particle(value: str) -> str:
    """한글 받침 여부에 따라 주제 조사 '은/는'을 고른다."""
    if not value:
        return "은"
    last = value[-1]
    code = ord(last) - 0xAC00
    if 0 <= code <= 0xD7A3 - 0xAC00:
        return "은" if code % 28 else "는"
    return "은"
