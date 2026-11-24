"""Tests for authentication and OAuth account verification."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gmail_calendar.auth import (
    load_credentials,
    run_interactive_oauth,
)
from gmail_calendar.config import SCOPES


def test_load_credentials_missing_token(temp_private_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"(?s)Google OAuth token not found at.*uv run auth"):
        load_credentials()


def test_load_credentials_insufficient_scopes(temp_private_dir: Path) -> None:
    token_path = temp_private_dir / "token.json"
    # Store unexpired token with only one scope
    token_path.write_text(
        json.dumps({
            "token": "fake-token",
            "refresh_token": "fake-refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "expiry": "2030-01-01T00:00:00Z",
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lacks required permissions"):
        load_credentials()


def test_load_credentials_account_mismatch(temp_private_dir: Path) -> None:
    token_path = temp_private_dir / "token.json"
    token_path.write_text(
        json.dumps({
            "token": "fake-token",
            "refresh_token": "fake-refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": SCOPES,
            "expiry": "2030-01-01T00:00:00Z",
        }),
        encoding="utf-8",
    )

    with patch("gmail_calendar.auth.get_authorized_email", return_value="other@gmail.com"):
        with pytest.raises(ValueError, match="Account mismatch: Token at.*belongs to 'other@gmail.com'"):
            load_credentials(expected_email="expected@gmail.com")


def test_load_credentials_success(temp_private_dir: Path) -> None:
    token_path = temp_private_dir / "token.json"
    token_path.write_text(
        json.dumps({
            "token": "fake-token",
            "refresh_token": "fake-refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": SCOPES,
            "expiry": "2030-01-01T00:00:00Z",
        }),
        encoding="utf-8",
    )

    with patch("gmail_calendar.auth.get_authorized_email", return_value="class@gmail.com"):
        creds = load_credentials(expected_email="class@gmail.com")
        assert creds is not None


def test_run_interactive_oauth_account_mismatch_never_saves(
    mock_client_secret: Path, temp_private_dir: Path
) -> None:
    token_path = temp_private_dir / "token.json"
    assert not token_path.exists()

    mock_flow_instance = MagicMock()
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = '{"token": "dummy"}'
    mock_flow_instance.run_local_server.return_value = mock_creds

    with patch("gmail_calendar.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow_instance), \
         patch("gmail_calendar.auth.get_authorized_email", return_value="unintended@gmail.com"):

        with pytest.raises(ValueError, match=r"(?s)Account mismatch!.*unintended@gmail.com"):
            run_interactive_oauth(expected_email="class@gmail.com", private_dir=temp_private_dir)

    # CRITICAL: Token file MUST NOT be created if email doesn't match
    assert not token_path.exists(), "token.json must NOT be saved on email mismatch!"


def test_run_interactive_oauth_account_match_saves_token(
    mock_client_secret: Path, temp_private_dir: Path
) -> None:
    token_path = temp_private_dir / "token.json"
    assert not token_path.exists()

    mock_flow_instance = MagicMock()
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = '{"token": "authorized-class-token"}'
    mock_flow_instance.run_local_server.return_value = mock_creds

    with patch("gmail_calendar.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow_instance), \
         patch("gmail_calendar.auth.get_authorized_email", return_value="class@gmail.com"):

        saved_path = run_interactive_oauth(expected_email="class@gmail.com", private_dir=temp_private_dir)

    assert saved_path == token_path
    assert token_path.exists()
    assert "authorized-class-token" in token_path.read_text(encoding="utf-8")


def test_run_interactive_oauth_never_silently_overwrites(
    mock_client_secret: Path, temp_private_dir: Path
) -> None:
    token_path = temp_private_dir / "token.json"
    token_path.write_text('{"token": "existing"}', encoding="utf-8")

    # Trying to authorize without overwrite=True must raise FileExistsError
    with pytest.raises(FileExistsError, match="Token file already exists"):
        run_interactive_oauth(expected_email="new_account@gmail.com", overwrite=False, private_dir=temp_private_dir)
