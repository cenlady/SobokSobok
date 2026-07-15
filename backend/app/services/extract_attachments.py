from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.normalized_policy import AttachmentFile


# kordoc이 처리하지 못하는 형식 (content_type 값 또는 확장자)
UNSUPPORTED_MARKERS = (
    "pptx",
    "ppt",
    "presentationml",
    "hangul-office",  # 혹시 모를 예외 케이스
)


def extract_pending_attachments_once() -> dict[str, int | bool]:
    """[서류 검토 영역] pending 첨부파일을 kordoc으로 파싱해 extracted_text를 채운다.

    - 대상: extraction_status == "pending" (설정 시 "failed" 포함)
    - 결과: extracted_text(마크다운) + extraction_status(success/empty/unsupported/failed)
    - 정규화 잡(normalize_policy_sources_once)과 동형 구조: advisory lock으로 잡을
      단일화하고, 행 단위 commit으로 한 파일 실패가 전체를 막지 않도록 한다.
    """
    db = SessionLocal()
    stats: dict[str, int | bool] = {
        "locked": False,
        "scanned": 0,
        "success": 0,
        "empty": 0,
        "unsupported": 0,
        "failed": 0,
        "skipped_missing_file": 0,
    }

    try:
        locked = _try_advisory_lock(db)
        stats["locked"] = locked
        if not locked:
            return stats

        target_statuses = ["pending"]
        if settings.EXTRACT_RETRY_FAILED:
            target_statuses.append("failed")

        query = (
            db.query(AttachmentFile)
            .filter(AttachmentFile.extraction_status.in_(target_statuses))
            .order_by(AttachmentFile.created_at)
        )
        if settings.EXTRACT_BATCH_LIMIT > 0:
            query = query.limit(settings.EXTRACT_BATCH_LIMIT)
        rows = query.all()

        for row in rows:
            stats["scanned"] = int(stats["scanned"]) + 1
            _process_row(db, row, stats)

        return stats
    finally:
        _release_advisory_lock(db)
        db.close()


def _process_row(db: Session, row: AttachmentFile, stats: dict[str, int | bool]) -> None:
    # 1) 미지원 형식 게이트 (재시도 무의미)
    if _is_unsupported(row):
        row.extraction_status = "unsupported"
        db.commit()
        stats["unsupported"] = int(stats["unsupported"]) + 1
        return

    # 2) 파일 존재 + 경로 안전성 검증
    resolved = _safe_storage_path(row.storage_path)
    if resolved is None or not resolved.is_file():
        row.extraction_status = "failed"
        db.commit()
        stats["skipped_missing_file"] = int(stats["skipped_missing_file"]) + 1
        stats["failed"] = int(stats["failed"]) + 1
        return

    # 3) 선점 (동시 실행 시 이중 처리 방지)
    row.extraction_status = "processing"
    db.commit()

    # 4) kordoc 실행
    try:
        content = _run_kordoc(str(resolved))
    except Exception as exc:  # noqa: BLE001 - 모든 추출 오류를 failed로 흡수
        row.extraction_status = "failed"
        db.commit()
        stats["failed"] = int(stats["failed"]) + 1
        print(
            f"pipeline_event feature=attachment_parsing parser=kordoc "
            f"stage=text_extraction status=error error_type={type(exc).__name__}",
            flush=True,
        )
        return

    # 5) 결과 정리 + 저장
    cleaned = (content or "").strip()
    if not cleaned:
        row.extracted_text = None
        row.extraction_status = "empty"
        db.commit()
        stats["empty"] = int(stats["empty"]) + 1
        return

    if len(cleaned) > settings.EXTRACT_MAX_CHARS:
        cleaned = cleaned[: settings.EXTRACT_MAX_CHARS]

    row.extracted_text = cleaned
    row.extraction_status = "success"
    db.commit()
    stats["success"] = int(stats["success"]) + 1
    print(
        f"pipeline_event feature=attachment_parsing parser=kordoc "
        f"stage=text_extraction output_chars={len(cleaned)} status=success",
        flush=True,
    )


def _run_kordoc(path: str) -> str:
    """kordoc CLI를 subprocess로 실행하고 추출 텍스트(마크다운)를 반환한다.

    `--silent`로 진행 로그를 stdout에서 제거하고 `--format json`으로 결과를 받아
    `success` 플래그로 성공 여부를 명확히 판정한다(마크다운 본문이 '{'로 시작해도
    오판하지 않도록). 실행 실패/타임아웃/파싱 오류는 예외로 전파해 호출부에서
    failed로 처리한다.
    """
    result = subprocess.run(
        [settings.KORDOC_CMD, "--silent", "--format", "json", path],
        capture_output=True,
        timeout=settings.KORDOC_TIMEOUT_SECONDS,
        check=True,
    )
    stdout = result.stdout.decode("utf-8", errors="replace")
    return _parse_kordoc_output(stdout)


def _parse_kordoc_output(stdout: str) -> str:
    """kordoc `--format json` 출력에서 markdown 본문을 뽑는다.

    kordoc은 `--silent`로도 일부 경고(`Warning: ...`)를 stdout에 흘리며, 그 뒤에
    JSON 결과가 붙는다. 따라서 첫 '{'부터 마지막 '}'까지를 JSON으로 간주해 파싱한다.
    스키마: {"success": bool, "fileType": str, "markdown": str, ...}
    success가 false거나 스키마가 어긋나면 예외를 던져 failed로 흘려보낸다.
    """
    stripped = stdout.strip()
    if not stripped:
        return ""
    payload = json.loads(_extract_json_blob(stripped))  # JSONDecodeError는 호출부에서 failed 처리
    if not isinstance(payload, dict):
        raise ValueError("kordoc 출력이 JSON 객체가 아닙니다")
    if payload.get("success") is False:
        raise RuntimeError(f"kordoc 파싱 실패: {payload.get('error') or payload}")
    markdown = payload.get("markdown")
    if not isinstance(markdown, str):
        raise ValueError("kordoc 출력에 markdown 필드가 없습니다")
    return markdown


def _extract_json_blob(text_value: str) -> str:
    """경고 로그가 앞에 섞인 stdout에서 JSON 객체 부분만 잘라낸다."""
    start = text_value.find("{")
    end = text_value.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("kordoc 출력에서 JSON 객체를 찾지 못했습니다")
    return text_value[start : end + 1]


def _is_unsupported(row: AttachmentFile) -> bool:
    return _is_unsupported_name(row.original_file_name, row.content_type)


def _is_unsupported_name(file_name: str | None, content_type: str | None) -> bool:
    """파일명/콘텐츠타입으로 kordoc 미지원 형식(PPTX 등)인지 판정한다."""
    haystacks = [
        (content_type or "").lower(),
        Path(file_name or "").suffix.lower().lstrip("."),
    ]
    return any(
        marker in value
        for value in haystacks
        if value
        for marker in UNSUPPORTED_MARKERS
    )


def _safe_storage_path(storage_path: str | None) -> Path | None:
    """storage_path가 ATTACHMENT_DIR 하위인지 검증해 디렉터리 탈출을 막는다."""
    if not storage_path:
        return None
    base = Path(settings.ATTACHMENT_DIR).resolve()
    try:
        resolved = Path(storage_path).resolve()
    except (OSError, ValueError):
        return None
    if base not in resolved.parents and resolved != base:
        # ATTACHMENT_DIR 밖이면 거부 (컨테이너 마운트 경로와 다를 수 있으니 경고만 남기고 허용하지 않음)
        return None
    return resolved


def _try_advisory_lock(db: Session) -> bool:
    if not settings.database_url.startswith("postgresql"):
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": settings.EXTRACTOR_ADVISORY_LOCK_ID},
        ).scalar()
    )


def _release_advisory_lock(db: Session) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": settings.EXTRACTOR_ADVISORY_LOCK_ID},
    )
    db.commit()
