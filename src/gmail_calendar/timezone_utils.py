"""Timezone utilities for Asia/Jerusalem.

Ensures all date/time inputs and outputs are correctly handled in
Asia/Jerusalem timezone, including daylight saving transitions.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from gmail_calendar.config import DEFAULT_TIMEZONE

JERUSALEM_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def get_jerusalem_tz() -> ZoneInfo:
    """Return the ZoneInfo object for Asia/Jerusalem."""
    return JERUSALEM_TZ


def parse_jerusalem_datetime(value: str | datetime) -> datetime:
    """Parse a datetime string or object into an aware datetime in Asia/Jerusalem timezone.

    Accepts:
    - ISO 8601 strings (e.g. '2026-11-24T10:00:00', '2026-11-24T10:00:00+02:00', '2026-11-24T08:00:00Z')
    - Date-only strings (e.g. '2026-11-24') which default to start of day 00:00:00.
    - Datetime objects (naive datetimes are assumed to be Asia/Jerusalem local time;
      aware datetimes are converted to Asia/Jerusalem).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=JERUSALEM_TZ)
        return value.astimezone(JERUSALEM_TZ)

    s = value.strip()
    # Normalize trailing 'Z' to UTC offset '+00:00' if present for fromisoformat compatibility
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Check date-only format YYYY-MM-DD
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            dt = datetime(d.year, d.month, d.day, 0, 0, 0)
        except ValueError as err:
            raise ValueError(
                f"Invalid date/time string: '{value}'. Expected ISO 8601 format, "
                f"e.g., '2026-11-24T14:30:00' or '2026-11-24'."
            ) from err

    if dt.tzinfo is None:
        return dt.replace(tzinfo=JERUSALEM_TZ)
    return dt.astimezone(JERUSALEM_TZ)


def format_jerusalem_iso(dt: datetime) -> str:
    """Format an aware datetime in Asia/Jerusalem timezone to ISO 8601 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JERUSALEM_TZ)
    else:
        dt = dt.astimezone(JERUSALEM_TZ)
    return dt.isoformat()


def find_free_intervals(
    window_start: datetime,
    window_end: datetime,
    busy_intervals: list[tuple[datetime, datetime]],
    duration_minutes: int,
) -> list[dict[str, Any]]:
    """Compute available free intervals of at least duration_minutes inside a time window.

    All datetime inputs must be aware or will be converted to Asia/Jerusalem.
    Returns a list of dicts with 'start', 'end', 'duration_minutes', and discrete 'slots'.
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive (> 0)")

    start = parse_jerusalem_datetime(window_start)
    end = parse_jerusalem_datetime(window_end)

    if end <= start:
        raise ValueError(
            f"window_end ({end.isoformat()}) must be after window_start ({start.isoformat()})"
        )

    # Normalize and clamp busy intervals to the window [start, end]
    clamped_busy: list[tuple[datetime, datetime]] = []
    for b_start_raw, b_end_raw in busy_intervals:
        b_start = parse_jerusalem_datetime(b_start_raw)
        b_end = parse_jerusalem_datetime(b_end_raw)
        if b_end <= start or b_start >= end:
            continue
        clamped_start = max(b_start, start)
        clamped_end = min(b_end, end)
        if clamped_end > clamped_start:
            clamped_busy.append((clamped_start, clamped_end))

    # Sort busy intervals by start time
    clamped_busy.sort(key=lambda x: x[0])

    # Merge overlapping or adjacent busy intervals
    merged_busy: list[tuple[datetime, datetime]] = []
    for interval in clamped_busy:
        if not merged_busy:
            merged_busy.append(interval)
        else:
            prev_start, prev_end = merged_busy[-1]
            if interval[0] <= prev_end:
                merged_busy[-1] = (prev_start, max(prev_end, interval[1]))
            else:
                merged_busy.append(interval)

    # Find free gaps between start and end
    req_delta = timedelta(minutes=duration_minutes)
    free_intervals: list[dict[str, Any]] = []

    cursor = start
    for b_start, b_end in merged_busy:
        if b_start > cursor:
            gap = b_start - cursor
            if gap >= req_delta:
                mins = int(gap.total_seconds() // 60)
                # Compute discrete slot options inside this gap
                slots = []
                slot_cur = cursor
                while slot_cur + req_delta <= b_start:
                    slots.append({
                        "start": format_jerusalem_iso(slot_cur),
                        "end": format_jerusalem_iso(slot_cur + req_delta),
                    })
                    slot_cur += req_delta

                free_intervals.append({
                    "start": format_jerusalem_iso(cursor),
                    "end": format_jerusalem_iso(b_start),
                    "duration_minutes": mins,
                    "available_slots": slots,
                })
        cursor = max(cursor, b_end)

    if cursor < end:
        gap = end - cursor
        if gap >= req_delta:
            mins = int(gap.total_seconds() // 60)
            slots = []
            slot_cur = cursor
            while slot_cur + req_delta <= end:
                slots.append({
                    "start": format_jerusalem_iso(slot_cur),
                    "end": format_jerusalem_iso(slot_cur + req_delta),
                })
                slot_cur += req_delta

            free_intervals.append({
                "start": format_jerusalem_iso(cursor),
                "end": format_jerusalem_iso(end),
                "duration_minutes": mins,
                "available_slots": slots,
            })

    return free_intervals
