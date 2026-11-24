"""Tests for Asia/Jerusalem timezone conversions and free slot finding."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from gmail_calendar.timezone_utils import (
    find_free_intervals,
    format_jerusalem_iso,
    get_jerusalem_tz,
    parse_jerusalem_datetime,
)


def test_jerusalem_tz_name() -> None:
    tz = get_jerusalem_tz()
    assert tz.key == "Asia/Jerusalem"


def test_parse_naive_datetime() -> None:
    dt = parse_jerusalem_datetime("2026-11-24T14:30:00")
    assert dt.tzinfo is not None
    assert dt.tzinfo.key == "Asia/Jerusalem"
    assert dt.hour == 14
    assert dt.minute == 30


def test_parse_aware_utc_datetime() -> None:
    # 12:00 UTC in November (IST, UTC+2) should be 14:00 Asia/Jerusalem
    dt = parse_jerusalem_datetime("2026-11-24T12:00:00Z")
    assert dt.tzinfo.key == "Asia/Jerusalem"
    assert dt.hour == 14


def test_daylight_saving_transitions() -> None:
    # Summer time in Israel (July): Israel Daylight Time (IDT, UTC+3)
    summer_dt = parse_jerusalem_datetime("2026-07-15T12:00:00")
    assert summer_dt.utcoffset() == timedelta(hours=3)

    # Winter time in Israel (January): Israel Standard Time (IST, UTC+2)
    winter_dt = parse_jerusalem_datetime("2026-01-15T12:00:00")
    assert winter_dt.utcoffset() == timedelta(hours=2)


def test_format_jerusalem_iso() -> None:
    dt = datetime(2026, 11, 24, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
    formatted = format_jerusalem_iso(dt)
    # 10:00 UTC = 12:00+02:00 in November Jerusalem time
    assert "2026-11-24T12:00:00+02:00" in formatted


def test_find_free_intervals_all_free() -> None:
    start = parse_jerusalem_datetime("2026-11-24T09:00:00")
    end = parse_jerusalem_datetime("2026-11-24T12:00:00")
    free = find_free_intervals(start, end, busy_intervals=[], duration_minutes=30)
    assert len(free) == 1
    assert free[0]["duration_minutes"] == 180
    assert len(free[0]["available_slots"]) == 6


def test_find_free_intervals_with_busy() -> None:
    start = parse_jerusalem_datetime("2026-11-24T09:00:00")
    end = parse_jerusalem_datetime("2026-11-24T12:00:00")
    busy = [
        (
            parse_jerusalem_datetime("2026-11-24T10:00:00"),
            parse_jerusalem_datetime("2026-11-24T11:00:00"),
        )
    ]
    free = find_free_intervals(start, end, busy_intervals=busy, duration_minutes=30)
    assert len(free) == 2
    # 09:00 - 10:00 (60 mins)
    assert free[0]["duration_minutes"] == 60
    assert len(free[0]["available_slots"]) == 2
    # 11:00 - 12:00 (60 mins)
    assert free[1]["duration_minutes"] == 60
    assert len(free[1]["available_slots"]) == 2


def test_find_free_intervals_overlapping_busy() -> None:
    start = parse_jerusalem_datetime("2026-11-24T09:00:00")
    end = parse_jerusalem_datetime("2026-11-24T13:00:00")
    busy = [
        (
            parse_jerusalem_datetime("2026-11-24T10:00:00"),
            parse_jerusalem_datetime("2026-11-24T11:00:00"),
        ),
        (
            parse_jerusalem_datetime("2026-11-24T10:30:00"),
            parse_jerusalem_datetime("2026-11-24T11:30:00"),
        ),
    ]
    free = find_free_intervals(start, end, busy_intervals=busy, duration_minutes=60)
    assert len(free) == 2
    # 09:00 - 10:00 (60 mins)
    assert free[0]["duration_minutes"] == 60
    # 11:30 - 13:00 (90 mins)
    assert free[1]["duration_minutes"] == 90


def test_find_free_intervals_gap_too_short_excluded() -> None:
    start = parse_jerusalem_datetime("2026-11-24T09:00:00")
    end = parse_jerusalem_datetime("2026-11-24T10:00:00")
    busy = [
        (
            parse_jerusalem_datetime("2026-11-24T09:20:00"),
            parse_jerusalem_datetime("2026-11-24T09:50:00"),
        )
    ]
    # Gaps are 20 mins and 10 mins. Requested duration is 30 mins -> 0 free intervals
    free = find_free_intervals(start, end, busy_intervals=busy, duration_minutes=30)
    assert len(free) == 0


def test_find_free_intervals_invalid_inputs() -> None:
    start = parse_jerusalem_datetime("2026-11-24T10:00:00")
    end = parse_jerusalem_datetime("2026-11-24T09:00:00")
    with pytest.raises(ValueError, match="window_end.*must be after window_start"):
        find_free_intervals(start, end, busy_intervals=[], duration_minutes=30)

    with pytest.raises(ValueError, match="duration_minutes must be positive"):
        find_free_intervals(end, start, busy_intervals=[], duration_minutes=0)
