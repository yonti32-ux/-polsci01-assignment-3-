"""Gmail operations for the gmail-calendar MCP server.

Implements search_emails, read_email, and create_draft using Google Gmail API.
No send or delete operations are implemented.
"""

from __future__ import annotations

import base64
import html
import re
from email.message import EmailMessage
from typing import Any


def _decode_base64url(data: str) -> str:
    """Safely decode base64url string with proper padding."""
    padded = data + "=" * (-len(data) % 4)
    try:
        raw_bytes = base64.urlsafe_b64decode(padded)
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body_text(payload: dict[str, Any]) -> str:
    """Recursively extract plain text or HTML body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    # If it's a simple plain text part with data
    if mime_type == "text/plain" and body_data:
        return _decode_base64url(body_data)

    # If multipart, look for parts
    parts = payload.get("parts", [])
    if parts:
        plain_texts: list[str] = []
        html_texts: list[str] = []

        for part in parts:
            part_mime = part.get("mimeType", "")
            part_body = part.get("body", {}).get("data")

            if part_mime == "text/plain" and part_body:
                plain_texts.append(_decode_base64url(part_body))
            elif part_mime == "text/html" and part_body:
                html_texts.append(_decode_base64url(part_body))
            elif "parts" in part:
                sub_text = _extract_body_text(part)
                if sub_text:
                    plain_texts.append(sub_text)

        if plain_texts:
            return "\n".join(plain_texts).strip()

        if html_texts:
            raw_html = "\n".join(html_texts)
            # Strip simple HTML tags for readability
            stripped = re.sub(r"<[^>]+>", " ", raw_html)
            return html.unescape(stripped).strip()

    # Fallback to direct body if available even if not text/plain
    if body_data:
        text = _decode_base64url(body_data)
        if "html" in mime_type:
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text).strip()
        return text

    return ""


def search_emails(
    service: Any,
    query: str = "",
    max_results: int = 10,
) -> list[dict[str, str]]:
    """Search Gmail messages with a query and bounded result count.

    Returns a list of dicts with message IDs, senders, subjects, and snippets.
    """
    # Bound max_results between 1 and 50
    bounded_max = max(1, min(int(max_results), 50))

    list_res = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=bounded_max)
        .execute()
    )

    messages = list_res.get("messages", [])
    results: list[dict[str, str]] = []

    for msg in messages:
        msg_id = msg["id"]
        try:
            detail = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
        except Exception:
            # Fallback to full format if metadata format is not supported by mock/API
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in detail.get("payload", {}).get("headers", [])
        }
        sender = headers.get("from", "Unknown Sender")
        subject = headers.get("subject", "(No Subject)")
        snippet = detail.get("snippet", "")

        results.append({
            "id": msg_id,
            "sender": sender,
            "subject": subject,
            "snippet": snippet,
        })

    return results


def read_email(service: Any, message_id: str) -> dict[str, Any]:
    """Read one Gmail message by ID and return its headers and decoded body text."""
    detail = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers_list = detail.get("payload", {}).get("headers", [])
    headers: dict[str, str] = {
        h.get("name", ""): h.get("value", "") for h in headers_list
    }

    body_text = _extract_body_text(detail.get("payload", {}))
    if not body_text:
        body_text = detail.get("snippet", "")

    return {
        "id": detail.get("id", message_id),
        "thread_id": detail.get("threadId", ""),
        "headers": headers,
        "body": body_text,
    }


def create_draft(
    service: Any,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """Save a Gmail draft with the provided details and return the draft ID."""
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc
    message.set_content(body)

    raw_bytes = message.as_bytes()
    raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("ascii")

    draft_body = {
        "message": {
            "raw": raw_b64,
        }
    }

    res = service.users().drafts().create(userId="me", body=draft_body).execute()

    return {
        "draft_id": res.get("id"),
        "message_id": res.get("message", {}).get("id"),
        "to": to,
        "subject": subject,
        "status": "draft_created",
    }
