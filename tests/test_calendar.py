"""Tests for Google Calendar operations using mocked API responses."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from gmail_calendar.calendar_ops import (
    create_event,
    find_free_slots,
    list_events,
)


def test_list_events_mocked() -> None:
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        "items": [
            {
                "id": "event1",
                "summary": "Team Sync",
                "start": {"dateTime": "2026-11-24T10:00:00+02:00"},
                "end": {"dateTime": "2026-11-24T11:00:00+02:00"},
                "description": "Weekly progress review",
                "status": "confirmed",
                "htmlLink": "https://calendar.google.com/event1",
            }
        ]
    }

    events = list_events(
        mock_service,
        start_time="2026-11-24T08:00:00",
        end_time="2026-11-24T18:00:00",
    )

    assert len(events) == 1
    assert events[0]["id"] == "event1"
    assert events[0]["title"] == "Team Sync"
    assert "2026-11-24T10:00:00+02:00" in events[0]["start"]
    assert "2026-11-24T11:00:00+02:00" in events[0]["end"]

    # Verify call parameters
    call_kwargs = mock_service.events().list.call_args.kwargs
    assert call_kwargs["calendarId"] == "primary"
    assert call_kwargs["singleEvents"] is True
    assert "timeMin" in call_kwargs
    assert "timeMax" in call_kwargs


def test_find_free_slots_mocked() -> None:
    mock_service = MagicMock()
    mock_service.freebusy().query().execute.return_value = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2026-11-25T11:00:00+02:00",
                        "end": "2026-11-25T12:00:00+02:00",
                    }
                ]
            }
        }
    }

    result = find_free_slots(
        mock_service,
        start_time="2026-11-25T09:00:00",
        end_time="2026-11-25T13:00:00",
        duration_minutes=60,
    )

    assert result["timezone"] == "Asia/Jerusalem"
    assert result["duration_minutes"] == 60
    assert result["total_free_intervals"] == 2

    # Free intervals: 09:00 - 11:00 (120 mins) and 12:00 - 13:00 (60 mins)
    intervals = result["free_intervals"]
    assert intervals[0]["duration_minutes"] == 120
    assert intervals[1]["duration_minutes"] == 60


def test_create_event_mocked() -> None:
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        "id": "new_event_123",
        "summary": "Office Hours",
        "start": {"dateTime": "2026-11-26T14:00:00+02:00"},
        "end": {"dateTime": "2026-11-26T15:00:00+02:00"},
        "description": "Discussing MCP assignment",
        "htmlLink": "https://calendar.google.com/new_event_123",
        "status": "confirmed",
    }

    res = create_event(
        mock_service,
        title="Office Hours",
        start_time="2026-11-26T14:00:00",
        end_time="2026-11-26T15:00:00",
        description="Discussing MCP assignment",
    )

    assert res["id"] == "new_event_123"
    assert res["title"] == "Office Hours"
    assert "2026-11-26T14:00:00+02:00" in res["start"]
    assert "2026-11-26T15:00:00+02:00" in res["end"]

    # Verify event body parameters
    call_kwargs = mock_service.events().insert.call_args.kwargs
    assert call_kwargs["calendarId"] == "primary"
    body = call_kwargs["body"]
    assert body["summary"] == "Office Hours"
    assert body["start"]["timeZone"] == "Asia/Jerusalem"
    assert body["end"]["timeZone"] == "Asia/Jerusalem"
    assert body["description"] == "Discussing MCP assignment"

    # CRITICAL: Verify attendees and invitations are strictly omitted
    assert "attendees" not in body, "Attendees MUST be omitted from event creation"
    assert "sendUpdates" not in call_kwargs, "Invitations/sendUpdates MUST be omitted"
