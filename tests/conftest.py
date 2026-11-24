"""Pytest fixtures and configuration for gmail-calendar tests."""

from __future__ import annotations

import os
from pathlib import Path
import pytest


@pytest.fixture
def temp_private_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture providing an isolated GOOGLE_PRIVATE_DIR with a dummy client_secret file."""
    priv_dir = tmp_path / "privet"
    priv_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOOGLE_PRIVATE_DIR", str(priv_dir))
    return priv_dir


@pytest.fixture
def mock_client_secret(temp_private_dir: Path) -> Path:
    """Create a dummy client_secret file in the temp private dir."""
    secret_path = temp_private_dir / "client_secret_test.json"
    secret_path.write_text(
        '{"installed": {"client_id": "test-id", "client_secret": "test-secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}',
        encoding="utf-8",
    )
    return secret_path
