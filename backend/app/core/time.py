from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def korea_now() -> datetime:
    """Return the current timezone-aware Korean local time."""

    return datetime.now(KOREA_TIMEZONE)


def korea_now_naive() -> datetime:
    """Return Korean local time for legacy timezone-naive policy columns.

    Policy application dates are parsed from Korean public notices and stored in
    PostgreSQL ``timestamp without time zone`` columns.  Comparisons therefore
    need a naive value too, but it must represent Asia/Seoul rather than the
    container's UTC clock.
    """

    return korea_now().replace(tzinfo=None)
