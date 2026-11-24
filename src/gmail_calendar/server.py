"""FastMCP server for Gmail and Google Calendar.

Exposes exactly six MCP tools:
1. search_emails
2. read_email
3. create_draft
4. list_events
5. find_free_slots
6. create_event

All diagnostics are logged to stderr so stdout remains reserved for JSON-RPC messages.
No send or delete operations or generic API tools are exposed.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

from gmail_calendar import calendar_ops, gmail_ops
from gmail_calendar.auth import load_credentials, log_stderr

# FastMCP server instance named "gmail-calendar"
mcp = FastMCP("gmail-calendar")

# Mockable factory hooks for testing
_gmail_service_override: Any | None = None
_calendar_service_override: Any | None = None


def set_service_overrides(
    gmail_service: Any | None = None,
    calendar_service: Any | None = None,
) -> None:
    """Override Google API services for testing without network/credentials."""
    global _gmail_service_override, _calendar_service_override
    _gmail_service_override = gmail_service
    _calendar_service_override = calendar_service


def get_gmail_service() -> Any:
    """Obtain authenticated Gmail API service client."""
    if _gmail_service_override is not None:
        return _gmail_service_override
    creds = load_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_calendar_service() -> Any:
    """Obtain authenticated Google Calendar API service client."""
    if _calendar_service_override is not None:
        return _calendar_service_override
    creds = load_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ============================================================================
# Tool 1: search_emails
# ============================================================================
@mcp.tool(
    name="search_emails",
    description=(
        "Search Gmail with a query string and a bounded result count. "
        "Returns message IDs, senders, subjects, and short snippets."
    ),
)
def search_emails(query: str = "", max_results: int = 10) -> list[dict[str, str]]:
    """Search Gmail with a query and a bounded result count. Return message IDs, senders, subjects, and short snippets."""
    try:
        service = get_gmail_service()
        return gmail_ops.search_emails(service, query=query, max_results=max_results)
    except Exception as err:
        log_stderr(f"[search_emails error] {err}")
        raise


# ============================================================================
# Tool 2: read_email
# ============================================================================
@mcp.tool(
    name="read_email",
    description=(
        "Read one Gmail message by its message ID. "
        "Returns the email headers (From, To, Subject, Date, etc.) and decoded body text."
    ),
)
def read_email(message_id: str) -> dict[str, Any]:
    """Read one message by ID and return its headers and body text."""
    try:
        service = get_gmail_service()
        return gmail_ops.read_email(service, message_id=message_id)
    except Exception as err:
        log_stderr(f"[read_email error] {err}")
        raise


# ============================================================================
# Tool 3: create_draft
# ============================================================================
@mcp.tool(
    name="create_draft",
    description=(
        "Save a Gmail draft and return its draft ID. "
        "Accepts recipient email (to), subject, body text, and optional cc and bcc. "
        "Does not send the email."
    ),
)
def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """Save a Gmail draft and return its draft ID."""
    try:
        service = get_gmail_service()
        return gmail_ops.create_draft(
            service, to=to, subject=subject, body=body, cc=cc, bcc=bcc
        )
    except Exception as err:
        log_stderr(f"[create_draft error] {err}")
        raise


# ============================================================================
# Tool 4: list_events
# ============================================================================
@mcp.tool(
    name="list_events",
    description=(
        "List events on the primary calendar in a given time range. "
        "start_time and end_time are parsed in Asia/Jerusalem timezone. "
        "Returns event IDs, titles, start and end times in Asia/Jerusalem, and descriptions."
    ),
)
def list_events(
    start_time: str,
    end_time: str,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List events on the primary calendar in a given time range."""
    try:
        service = get_calendar_service()
        return calendar_ops.list_events(
            service,
            start_time=start_time,
            end_time=end_time,
            max_results=max_results,
        )
    except Exception as err:
        log_stderr(f"[list_events error] {err}")
        raise


# ============================================================================
# Tool 5: find_free_slots
# ============================================================================
@mcp.tool(
    name="find_free_slots",
    description=(
        "Find available intervals of a requested duration inside a supplied time window "
        "using the primary calendar's free/busy data. "
        "All calculations and outputs use Asia/Jerusalem local date and time."
    ),
)
def find_free_slots(
    start_time: str,
    end_time: str,
    duration_minutes: int = 30,
) -> dict[str, Any]:
    """Find available intervals of a requested duration inside a supplied time window using the primary calendar's free/busy data."""
    try:
        service = get_calendar_service()
        return calendar_ops.find_free_slots(
            service,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
        )
    except Exception as err:
        log_stderr(f"[find_free_slots error] {err}")
        raise


# ============================================================================
# Tool 6: create_event
# ============================================================================
@mcp.tool(
    name="create_event",
    description=(
        "Create an event on the primary calendar with a title, start, end, and optional description. "
        "Times are set in Asia/Jerusalem. Attendees and invitations are strictly omitted."
    ),
)
def create_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create an event on the primary calendar with a title, start, end, and optional description. Omit attendees and invitations."""
    try:
        service = get_calendar_service()
        return calendar_ops.create_event(
            service,
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
        )
    except Exception as err:
        log_stderr(f"[create_event error] {err}")
        raise


def check_token_status() -> bool:
    """Check whether token.json exists and is valid without failing ungracefully."""
    try:
        load_credentials()
        return True
    except FileNotFoundError as err:
        log_stderr(f"\n[gmail-calendar warning] {err}\n")
        return False
    except Exception as err:
        log_stderr(f"\n[gmail-calendar warning] Failed to validate credentials: {err}\n")
        return False


def main() -> None:
    """Run FastMCP gmail-calendar server over stdio.

    All diagnostic output is sent to stderr; stdout is kept strictly clean
    for MCP JSON-RPC protocol communication.
    """
    log_stderr("Starting gmail-calendar FastMCP server over stdio...")
    check_token_status()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
