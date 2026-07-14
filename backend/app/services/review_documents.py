from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rag_utils import EmbeddingModel, OllamaEmbeddingModel
from app.models.normalized_policy import NormalizedPolicy
from app.models.review import ReviewSession, ReviewUpload, ReviewVector
from app.services.document_guides import get_guide
from app.services.extract_attachments import _run_kordoc, _is_unsupported_name


@dataclass
class UploadedFile:
    """API가 받은 파일 하나. 서비스는 UploadFile을 직접 다루지 않는다."""

    file_bytes: bytes
    original_file_name: str
    content_type: str | None


# 요건 대조를 '할 수 있었는가'를 나타내는 세 상태.
#
# 빈 requirement_matches를 "요건을 다 충족했다"로 읽으면 안 된다.
# 활성 정책 471건 중 297건(63%)은 공고에 필수서류가 명시돼 있지 않아 요건 벡터가 아예 없다.
# "요건이 없다"와 "요건을 충족했다"는 전혀 다른 얘기고, 후자로 보여주면 근거 없이
# 사용자를 안심시키게 된다. 서류 검토 도구로서 가장 나쁜 실패다.
REQ_NOT_REQUESTED = "not_requested"  # 정책을 고르지 않았다
REQ_NO_DATA = "no_requirement_data"  # 정책은 골랐지만 공고에 필수서류가 없다
REQ_MATCHED = "matched"  # 실제로 대조했다


def create_review_session(
    db: Session,
    *,
    files: list[UploadedFile],
    policy: NormalizedPolicy | None = None,
    user_id: int | None = None,
) -> ReviewSession:
    """업로드 파일들을 저장하고 queued 상태의 검토 세션을 만든다.

    검토 본체(run_review_pipeline)는 백그라운드에서 돈다. API는 세션 id만 즉시
    돌려주고, 프론트는 그 id로 진행 상태를 폴링한다.
    """
    session = ReviewSession(
        user_id=user_id,
        policy_id=policy.id if policy else None,
        review_status="queued",
        requirement_status=REQ_NOT_REQUESTED if policy is None else REQ_MATCHED,
    )
    db.add(session)
    db.flush()  # id 발급

    base = Path(settings.REVIEW_UPLOAD_DIR)
    base.mkdir(parents=True, exist_ok=True)

    for item in files:
        suffix = Path(item.original_file_name or "").suffix
        stored_path = base / f"{uuid.uuid4().hex}{suffix}"
        stored_path.write_bytes(item.file_bytes)

        db.add(
            ReviewUpload(
                session_id=session.id,
                original_file_name=item.original_file_name,
                storage_path=str(stored_path),
                content_type=item.content_type,
                file_size=len(item.file_bytes),
                extraction_status="pending",
            )
        )

    db.commit()
    db.refresh(session)
    return session


def run_review_pipeline(
    db: Session,
    session: ReviewSession,
    policy: NormalizedPolicy | None = None,
    embedding_model: EmbeddingModel | None = None,
) -> ReviewSession:
    """검토 세션을 처리한다. 파일 여러 개를 함께 본다.

    흐름:
      1. 파일마다 kordoc으로 텍스트 추출                   (review_status=extracting)
      2. 파일마다 자체 검토(오타·빈칸·형식) + 서류 유형 판정  (diagnosing)
      3. 판정된 유형으로 정책 필수서류와 1:1 배정            (matching)

    ── 진단이 대조보다 '먼저'인 이유

    요건 대조에 LLM이 판정한 서류 유형(document_type)을 쓴다. 서류 본문을 임베딩해
    대조하면 한국 행정문서는 어휘가 비슷해 무엇을 넣어도 임계값을 넘긴다
    (_match_requirements 주석 참고). 그래서 진단을 먼저 돌려 유형을 얻는다.

    ── 요건 대조가 파일별이 아니라 세션 전체 기준인 이유

    사업자등록증과 소득금액증명을 함께 올렸으면 둘 다 충족으로 봐야 한다. 파일별로
    대조하면 각 파일이 나머지 요건을 전부 '누락'으로 보고하게 된다.

    각 단계 진입 시 즉시 커밋한다. 커밋하지 않으면 트랜잭션이 끝나지 않아 폴링하는
    쪽에서는 계속 queued만 보인다.
    """
    # ── 1) 텍스트 추출 ──────────────────────────────────────────────
    _advance(db, session, "extracting")

    for upload in session.uploads:
        _extract_one(db, upload)

    readable = [u for u in session.uploads if u.extraction_status == "success" and u.extracted_text]
    if not readable:
        session.requirement_status = REQ_NOT_REQUESTED if policy is None else REQ_NO_DATA
        session.summary = "올린 서류에서 텍스트를 읽지 못했습니다. 스캔 이미지이거나 지원하지 않는 형식일 수 있어요."
        session.review_status = "failed"
        db.commit()
        return session

    # ── 2) 파일별 진단 (서류 유형 판정 포함) ─────────────────────────
    _advance(db, session, "diagnosing")

    for upload in readable:
        upload.diagnosis = _diagnose_one(upload, policy)
        db.commit()  # 파일 하나 끝날 때마다 반영 — 진행을 볼 수 있게

    # ── 3) 요건 대조 (정책이 있고, 그 정책에 요건 데이터가 있을 때만) ──
    matches: list[dict] = []
    requirement_status = REQ_NOT_REQUESTED

    if policy is not None:
        if not has_requirement_data(db, policy):
            # 공고에 필수서류가 명시돼 있지 않은 정책이다. 대조할 게 없으니 임베딩도
            # 돌리지 않는다. 그리고 이 사실을 숨기지 않는다.
            requirement_status = REQ_NO_DATA
        else:
            _advance(db, session, "matching")
            matches = _match_requirements(db, policy, readable, embedding_model)
            requirement_status = REQ_MATCHED

    session.requirement_status = requirement_status
    session.requirement_matches = matches
    session.summary = _summarize(session, readable, policy, matches, requirement_status)
    session.review_status = "done"
    db.commit()
    return session


# ────────────────────────────── 추출 ──────────────────────────────


def _extract_one(db: Session, upload: ReviewUpload) -> None:
    """파일 하나에서 텍스트를 뽑는다. 실패해도 다른 파일을 막지 않는다."""
    if _is_unsupported_name(upload.original_file_name, upload.content_type):
        upload.extraction_status = "unsupported"
        db.commit()
        return

    try:
        extracted = (_run_kordoc(upload.storage_path) or "").strip()
    except Exception as exc:  # noqa: BLE001 - 한 파일이 세션 전체를 막지 않게
        print(f"[review] 추출 실패 {upload.original_file_name}: {exc}", flush=True)
        upload.extraction_status = "failed"
        db.commit()
        return

    if not extracted:
        upload.extraction_status = "empty"
        db.commit()
        return

    upload.extracted_text = extracted
    upload.extraction_status = "success"
    db.commit()


# ──────────────────────────── 요건 대조 ────────────────────────────


def has_requirement_data(db: Session, policy: NormalizedPolicy) -> bool:
    """이 정책에 대조할 필수서류 요건 데이터가 있는가."""
    return (
        db.query(ReviewVector.id)
        .filter(
            ReviewVector.policy_id == policy.id,
            ReviewVector.document_type == "required_document",
        )
        .first()
        is not None
    )


def _match_requirements(
    db: Session,
    policy: NormalizedPolicy,
    uploads: list[ReviewUpload],
    embedding_model: EmbeddingModel | None,
) -> list[dict]:
    """올린 서류들을 정책 필수서류에 1:1로 배정한다.

    ── 왜 서류 '본문'이 아니라 LLM이 판정한 '유형명'으로 대조하는가

    본문(1000자 청크)을 임베딩해 대조하면 정확도가 처참하다. 한국 행정문서는 어휘가
    비슷해서, 소득금액증명서 한 장이 '외국인등록사실증명'(0.58), '국내거소신고사실증명'
    (0.56)까지 전부 임계값을 넘겨버린다. 무엇을 넣어도 다 통과한다.

    반면 LLM은 그 파일이 무슨 서류인지 정확히 안다("사업자등록증", "소득금액증명서").
    그 판정과 요건명을 이름 대 이름으로 재면 정답이 압도적 1등으로 올라온다.

        사업자등록증명  ← 사업자등록증     0.9174   (2등 0.69)
        소득금액증명   ← 소득금액증명서    0.9115   (2등 0.76)

    ── 왜 임계값이 아니라 '1등만'인가

    그래도 절대 임계값으로는 못 가른다. 오답도 0.68~0.76이라 0.55든 0.7이든 다 넘는다.
    한국 행정문서명은 어휘가 겹쳐서 절대값으로는 영원히 못 자른다.

    그래서 임계값을 버리고 배정 문제로 바꿨다. 파일 하나는 '가장 잘 맞는 요건 하나'만
    커버한다. 한 요건을 두 파일이 노리면 점수가 높은 쪽이 가져가고, 진 쪽은 자기 차선
    요건으로 간다(탐욕적 배정). 파일 수만큼만 커버되므로 근거 없이 부풀지 않는다.
    """
    requirements = (
        db.query(ReviewVector)
        .filter(
            ReviewVector.policy_id == policy.id,
            ReviewVector.document_type == "required_document",
        )
        .all()
    )
    if not requirements:
        return []

    # 진단이 끝나 document_type이 있는 파일만 대상. 못 읽었거나 유형을 모르는 건 뺀다.
    typed = [
        (u, (u.diagnosis or {}).get("document_type", "").strip())
        for u in uploads
    ]
    typed = [(u, t) for u, t in typed if t and t != "unknown"]
    if not typed:
        return _uncovered(requirements)

    embedder = embedding_model or OllamaEmbeddingModel(
        model_name=settings.REVIEW_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    type_vectors = embedder.embed_documents([t for _, t in typed])

    # (점수, 파일 인덱스, 요건 인덱스)를 전부 만들어 점수 높은 순으로 배정한다.
    scored: list[tuple[float, int, int]] = []
    for fi, vector in enumerate(type_vectors):
        for ri, req in enumerate(requirements):
            scored.append((_cosine(req.embedding, vector), fi, ri))
    scored.sort(reverse=True)

    # 요건 하나엔 파일 하나, 파일 하나는 요건 하나. 탐욕적으로 1등부터 짝지운다.
    assigned: dict[int, tuple[str, float]] = {}  # 요건 인덱스 → (파일명, 점수)
    used_files: set[int] = set()
    for score, fi, ri in scored:
        if fi in used_files or ri in assigned:
            continue
        # 이름 대 이름인데도 이 정도면 아예 다른 서류다. 최소한의 방어선.
        if score < settings.REVIEW_CANDIDATE_THRESHOLD:
            continue
        upload = typed[fi][0]
        assigned[ri] = (upload.original_file_name or "이름 없는 파일", score)
        used_files.add(fi)

    matches: list[dict] = []
    for ri, req in enumerate(requirements):
        hit = assigned.get(ri)
        matches.append(
            {
                "document_name": req.document_name,
                "best_similarity": round(float(hit[1]), 4) if hit else 0.0,
                # '확정'이 아니라 '후보'다. 이름을 likely_covered로 둔 이유.
                "likely_covered": hit is not None,
                "matched_file": hit[0] if hit else None,
                # 아직 없는 서류라면 "어디서 떼는지"를 알려준다. 목록만 던지는 건 절반이다.
                "guide": _guide_dict(req.document_name),
            }
        )

    matches.sort(key=lambda m: (not m["likely_covered"], -m["best_similarity"]))
    return matches


def _uncovered(requirements: list[ReviewVector]) -> list[dict]:
    """읽을 수 있는 서류가 없을 때 — 모든 요건이 미확인이다."""
    return [
        {
            "document_name": req.document_name,
            "best_similarity": 0.0,
            "likely_covered": False,
            "matched_file": None,
            "guide": _guide_dict(req.document_name),
        }
        for req in requirements
    ]


def _guide_dict(document_name: str) -> dict | None:
    """서류 발급 가이드. 아직 정리되지 않은 서류면 None."""
    guide = get_guide(document_name)
    if guide is None:
        return None
    return {
        "issuer": guide.issuer,
        "online": guide.online,
        "online_url": guide.online_url,
        "offline": guide.offline,
        "duration": guide.duration,
        "fee": guide.fee,
        "tip": guide.tip,
    }


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ───────────────────────────── LLM 진단 ─────────────────────────────


def _diagnose_one(upload: ReviewUpload, policy: NormalizedPolicy | None) -> dict:
    """파일 하나의 자체 검토(오타·빈칸·형식).

    요건 대조는 여기서 하지 않는다. 그건 세션 전체 기준이고, 파일 하나만 보고
    "다른 서류가 없다"고 말하면 안 된다.
    """
    prompt = _build_file_prompt(
        (upload.extracted_text or "")[:6000],
        upload.original_file_name or "",
        policy,
    )
    try:
        parsed = _parse_llm_json(_call_ollama_generate(prompt))
        if parsed is not None:
            return parsed
    except Exception as exc:  # noqa: BLE001
        print(f"[review] LLM 진단 실패 {upload.original_file_name}: {exc}", flush=True)

    return _fallback_result("이 서류의 자동 진단에 실패했습니다.")


def _build_file_prompt(extracted: str, file_name: str, policy: NormalizedPolicy | None) -> str:
    context = f"이 서류는 '{policy.title}' 신청용으로 추정됩니다.\n" if policy else ""

    return f"""당신은 소상공인 정책 신청 서류를 꼼꼼히 검토하는 전문가입니다.
{context}업로드된 서류 한 건의 '완성도'를 검토하세요.

[검토 관점]
- 오타/맞춤법: 잘못 쓰인 단어, 띄어쓰기 오류
- 빠진 항목: 비어 있는 칸, 미작성 필수 항목(성명·연락처·날짜·서명 등)
- 형식 오류: 날짜/금액 표기, 표·양식이 어긋난 부분

[중요] 이 서류 '안'만 보세요.
다른 서류가 필요한지는 판단하지 마세요. 그건 별도로 처리합니다.
"○○증명서도 필요합니다" 같은 말을 쓰지 마세요.

[파일명] {file_name}
[서류 원문(일부)]
{extracted}

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 쓰지 마세요.
해당 항목이 없으면 빈 배열([])로 두세요.
{{
  "document_type": "서류로 추정되는 유형(예: 사업자등록증, 사업계획서)",
  "typos": ["오타/맞춤법 지적"],
  "missing_fields": ["비어 있거나 미작성된 항목"],
  "format_issues": ["형식/양식 오류"],
  "improvement_points": ["보완이 필요한 점"],
  "overall": "1~2문장 진단"
}}"""


def _summarize(
    session: ReviewSession,
    readable: list[ReviewUpload],
    policy: NormalizedPolicy | None,
    matches: list[dict],
    requirement_status: str,
) -> str:
    """세션 종합 한두 문장. LLM을 또 부르지 않고 사실만 조합한다.

    여기서 LLM을 한 번 더 부르면 시간이 배로 들고, 이미 파일별 진단과 요건 대조라는
    '사실'이 다 나와 있어서 지어낼 게 없다. 사실을 조합하는 편이 정확하고 빠르다.
    """
    issue_count = sum(
        len(u.diagnosis.get("typos", []))
        + len(u.diagnosis.get("missing_fields", []))
        + len(u.diagnosis.get("format_issues", []))
        for u in readable
        if u.diagnosis
    )
    failed = [u for u in session.uploads if u.extraction_status != "success"]

    parts: list[str] = [f"서류 {len(readable)}건을 검토했습니다."]

    if issue_count:
        parts.append(f"보완이 필요한 항목이 {issue_count}건 있습니다.")
    else:
        parts.append("서류 자체에서 발견된 문제는 없습니다.")

    if requirement_status == REQ_MATCHED:
        missing = [m["document_name"] for m in matches if not m["likely_covered"]]
        if missing:
            parts.append(f"정책이 요구하는 서류 중 {len(missing)}건이 아직 확인되지 않았습니다.")
        else:
            parts.append("정책이 요구하는 서류는 모두 확인되었습니다.")
    elif requirement_status == REQ_NO_DATA and policy is not None:
        # 모르는 것은 모른다고 한다. "다 준비됐다"고 하면 거짓 안심이 된다.
        parts.append("이 정책은 공고에 필수 서류가 명시되어 있지 않아 요건 대조는 하지 못했습니다.")

    if failed:
        parts.append(f"읽지 못한 파일이 {len(failed)}건 있습니다.")

    return " ".join(parts)


def _call_ollama_generate(prompt: str) -> str:
    with httpx.Client(timeout=settings.REVIEW_LLM_TIMEOUT_SECONDS) as client:
        resp = client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.REVIEW_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _parse_llm_json(raw: str) -> dict | None:
    """LLM 출력은 신뢰할 수 없는 입력으로 취급한다. format:json을 줘도 완전히 믿지 않는다."""
    raw = (raw or "").strip()
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "document_type": str(data.get("document_type") or "unknown"),
        "typos": _as_str_list(data.get("typos")),
        "missing_fields": _as_str_list(data.get("missing_fields")),
        "format_issues": _as_str_list(data.get("format_issues")),
        "improvement_points": _as_str_list(data.get("improvement_points")),
        "overall": str(data.get("overall") or ""),
    }


def _as_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _fallback_result(message: str) -> dict:
    return {
        "document_type": "unknown",
        "typos": [],
        "missing_fields": [],
        "format_issues": [],
        "improvement_points": [],
        "overall": message,
    }


def _advance(db: Session, session: ReviewSession, stage: str) -> None:
    """진행 단계를 기록하고 즉시 커밋한다. 폴링하는 쪽이 볼 수 있어야 한다."""
    session.review_status = stage
    db.commit()
