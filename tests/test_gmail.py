"""Tests for Gmail operations using mocked API responses."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock
import pytest

from gmail_calendar.gmail_ops import (
    create_draft,
    read_email,
    search_emails,
)


def test_search_emails_mocked() -> None:
    mock_service = MagicMock()
    # Mock messages().list()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}]
    }
    # Mock messages().get() for metadata
    def mock_get(userId, id, **kwargs):
        req = MagicMock()
        if id == "msg1":
            req.execute.return_value = {
                "id": "msg1",
                "snippet": "Hello snippet 1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "Subject", "value": "Class Project Update"},
                    ]
                },
            }
        else:
            req.execute.return_value = {
                "id": "msg2",
                "snippet": "Hello snippet 2",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "bob@example.com"},
                        {"name": "Subject", "value": "Homework 06"},
                    ]
                },
            }
        return req

    mock_service.users().messages().get.side_effect = mock_get

    results = search_emails(mock_service, query="label:INBOX", max_results=5)
    assert len(results) == 2
    assert results[0] == {
        "id": "msg1",
        "sender": "alice@example.com",
        "subject": "Class Project Update",
        "snippet": "Hello snippet 1",
    }
    assert results[1]["sender"] == "bob@example.com"


def test_read_email_multipart_mocked() -> None:
    mock_service = MagicMock()
    encoded_body = base64.urlsafe_b64encode(b"This is the email plain body text.").decode("ascii")

    mock_service.users().messages().get().execute.return_value = {
        "id": "msg123",
        "threadId": "th456",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "teacher@university.edu"},
                {"name": "To", "value": "student@university.edu"},
                {"name": "Subject", "value": "Assignment Instructions"},
                {"name": "Date", "value": "Tue, 24 Nov 2026 10:00:00 +0200"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_body},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<p>HTML</p>").decode("ascii")},
                },
            ],
        },
    }

    result = read_email(mock_service, message_id="msg123")
    assert result["id"] == "msg123"
    assert result["headers"]["From"] == "teacher@university.edu"
    assert result["headers"]["Subject"] == "Assignment Instructions"
    assert result["body"] == "This is the email plain body text."


def test_create_draft_mocked() -> None:
    mock_service = MagicMock()
    mock_service.users().drafts().create().execute.return_value = {
        "id": "draft_789",
        "message": {"id": "msg_draft_789"},
    }

    result = create_draft(
        mock_service,
        to="recipient@example.com",
        subject="Draft Subject",
        body="Draft message body content",
        cc="cc@example.com",
    )

    assert result["draft_id"] == "draft_789"
    assert result["message_id"] == "msg_draft_789"
    assert result["status"] == "draft_created"

    # Verify drafts().create() was called with raw email
    call_args = mock_service.users().drafts().create.call_args
    assert call_args is not None
    body_sent = call_args.kwargs.get("body", {})
    raw_b64 = body_sent.get("message", {}).get("raw")
    assert raw_b64 is not None

    decoded_msg = base64.urlsafe_b64decode(raw_b64.encode("ascii")).decode("utf-8")
    assert "To: recipient@example.com" in decoded_msg
    assert "Subject: Draft Subject" in decoded_msg
    assert "Cc: cc@example.com" in decoded_msg
    assert "Draft message body content" in decoded_msg
