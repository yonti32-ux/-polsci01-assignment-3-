"""Google Calendar operations for the gmail-calendar MCP server.

Implements list_events, find_free_slots, and create_event using Google Calendar API.
All date/time operations are normalized to Asia/Jerusalem.
Attendees and invitations are explicitly omitted from event creation.
"""

from __future__ import annotations

from typing import Any

from gmail_calendar.timezone_utils import (
    find_free_intervals,
    format_jerusalem_iso,
    parse_jerusalem_datetime,
)


def list_events(
    service: Any,
    start_time: str,
    end_time: str,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List events on the primary calendar within the specified time range.

    Inputs start_time and end_time are parsed in Asia/Jerusalem timezone.
    Returns a list of events with times normalized to Asia/Jerusalem.
    """
    dt_start = parse_jerusalem_datetime(start_time)
    dt_end = parse_jerusalem_datetime(end_time)

    if dt_end <= dt_start:
        raise ValueError(
            f"end_time ({dt_end.isoformat()}) must be after start_time ({dt_start.isoformat()})"
        )

    bounded_max = max(1, min(int(max_results), 250))

    events_res = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=dt_start.isoformat(),
            timeMax=dt_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=bounded_max,
        )
        .execute()
    )

    items = events_res.get("items", [])
    results: list[dict[str, Any]] = []

    for item in items:
        # Start and end can be dateTime or date (for all-day events)
        raw_start = item.get("start", {})
        raw_end = item.get("end", {})

        if "dateTime" in raw_start:
            event_start = format_jerusalem_iso(parse_jerusalem_datetime(raw_start["dateTime"]))
        else:
            event_start = raw_start.get("date", "")

        if "dateTime" in raw_end:
            event_end = format_jerusalem_iso(parse_jerusalem_datetime(raw_end["dateTime"]))
        else:
            event_end = raw_end.get("date", "")

        results.append({
            "id": item.get("id"),
            "title": item.get("summary", "(Untitled Event)"),
            "start": event_start,
            "end": event_end,
            "description": item.get("description", ""),
            "status": item.get("status", "confirmed"),
            "html_link": item.get("htmlLink", ""),
        })

    return results


def find_free_slots(
    service: Any,
    start_time: str,
    end_time: str,
    duration_minutes: int,
) -> dict[str, Any]:
    """Find available intervals of requested duration inside a time window using free/busy data.

    Queries the primary calendar's free/busy schedule and returns free intervals
    and discrete slots formatted in Asia/Jerusalem.
    """
    dt_start = parse_jerusalem_datetime(start_time)
    dt_end = parse_jerusalem_datetime(end_time)

    if dt_end <= dt_start:
        raise ValueError(
            f"end_time ({dt_end.isoformat()}) must be after start_time ({dt_start.isoformat()})"
        )
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be greater than 0")

    freebusy_body = {
        "timeMin": dt_start.isoformat(),
        "timeMax": dt_end.isoformat(),
        "timeZone": "Asia/Jerusalem",
        "items": [{"id": "primary"}],
    }

    res = service.freebusy().query(body=freebusy_body).execute()
    busy_list = res.get("calendars", {}).get("primary", {}).get("busy", [])

    busy_intervals = [
        (
            parse_jerusalem_datetime(item["start"]),
            parse_jerusalem_datetime(item["end"]),
        )
        for item in busy_list
        if "start" in item and "end" in item
    ]

    intervals = find_free_intervals(
        window_start=dt_start,
        window_end=dt_end,
        busy_intervals=busy_intervals,
        duration_minutes=duration_minutes,
    )

    return {
        "timezone": "Asia/Jerusalem",
        "window": {
            "start": format_jerusalem_iso(dt_start),
            "end": format_jerusalem_iso(dt_end),
        },
        "duration_minutes": duration_minutes,
        "free_intervals": intervals,
        "total_free_intervals": len(intervals),
    }


def create_event(
    service: Any,
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create an event on the primary calendar with title, start, end, and optional description.

    Attendees and invitations are explicitly omitted.
    Times are parsed and set in Asia/Jerusalem timezone.
    """
    if not title.strip():
        raise ValueError("Event title cannot be empty")

    dt_start = parse_jerusalem_datetime(start_time)
    dt_end = parse_jerusalem_datetime(end_time)

    if dt_end <= dt_start:
        raise ValueError(
            f"end_time ({dt_end.isoformat()}) must be after start_time ({dt_start.isoformat()})"
        )

    event_body: dict[str, Any] = {
        "summary": title.strip(),
        "start": {
            "dateTime": dt_start.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
        "end": {
            "dateTime": dt_end.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
    }

    if description:
        event_body["description"] = description.strip()

    # Omit attendees and invitations entirely: do NOT pass 'attendees' or 'sendUpdates'
    res = service.events().insert(calendarId="primary", body=event_body).execute()

    return {
        "id": res.get("id"),
        "title": res.get("summary"),
        "start": format_jerusalem_iso(dt_start),
        "end": format_jerusalem_iso(dt_end),
        "description": res.get("description", ""),
        "html_link": res.get("htmlLink", ""),
        "status": res.get("status", "confirmed"),
    }
