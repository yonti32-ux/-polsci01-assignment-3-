"""Tests for configuration and client_secret discovery."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from gmail_calendar.config import (
    find_client_secret,
    get_private_dir,
    get_token_path,
)


def test_private_dir_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_PRIVATE_DIR", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_PRIVATE_DIR.*is not set"):
        get_private_dir()


def test_private_dir_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    non_existent = tmp_path / "does_not_exist"
    monkeypatch.setenv("GOOGLE_PRIVATE_DIR", str(non_existent))
    with pytest.raises(FileNotFoundError, match="does not exist"):
        get_private_dir()


def test_find_client_secret_zero_matches(temp_private_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No Google Desktop OAuth client secret file"):
        find_client_secret(temp_private_dir)


def test_find_client_secret_multiple_matches(temp_private_dir: Path) -> None:
    (temp_private_dir / "client_secret_1.json").write_text("{}", encoding="utf-8")
    (temp_private_dir / "client_secret_2.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple client secret files matching"):
        find_client_secret(temp_private_dir)


def test_find_client_secret_single_match(mock_client_secret: Path, temp_private_dir: Path) -> None:
    found = find_client_secret(temp_private_dir)
    assert found == mock_client_secret


def test_get_token_path(temp_private_dir: Path) -> None:
    token_p = get_token_path(temp_private_dir)
    assert token_p == temp_private_dir / "token.json"
