"""Configuration and path management for gmail-calendar MCP server.

Handles GOOGLE_PRIVATE_DIR resolution, client secret discovery,
and token file paths while ensuring credentials are never exposed or copied.
"""

from __future__ import annotations

import os
from pathlib import Path

# Minimal OAuth scopes needed for operations:
# - gmail.readonly: search_emails, read_email, getProfile (to verify class account)
# - gmail.compose: create_draft (strictly draft creation, no send/delete)
# - calendar.events: list_events, create_event (events on primary calendar)
# - calendar.freebusy: find_free_slots (query free/busy data on primary calendar)
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
]

DEFAULT_TIMEZONE: str = "Asia/Jerusalem"
ENV_PRIVATE_DIR_KEY: str = "GOOGLE_PRIVATE_DIR"
ENV_CLASS_EMAIL_KEY: str = "CLASS_EMAIL"
TOKEN_FILENAME: str = "token.json"


def get_private_dir() -> Path:
    """Retrieve and validate the private directory path from GOOGLE_PRIVATE_DIR."""
    raw_dir = os.environ.get(ENV_PRIVATE_DIR_KEY)
    if not raw_dir:
        raise ValueError(
            f"Environment variable '{ENV_PRIVATE_DIR_KEY}' is not set. "
            f"Please set it to your private folder path "
            f"(e.g., in PowerShell: $env:{ENV_PRIVATE_DIR_KEY} = 'C:\\uoh\\privet')."
        )
    path = Path(raw_dir).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Directory specified by {ENV_PRIVATE_DIR_KEY} does not exist: '{path}'. "
            f"Please create the directory and place your Google Desktop OAuth client secret in it."
        )
    if not path.is_dir():
        raise NotADirectoryError(
            f"Path specified by {ENV_PRIVATE_DIR_KEY} is not a directory: '{path}'."
        )
    return path


def find_client_secret(private_dir: Path | None = None) -> Path:
    """Locate the single client_secret*.json file in GOOGLE_PRIVATE_DIR.

    Raises FileNotFoundError if zero matches are found.
    Raises ValueError if multiple matches are found, listing their names so the user
    can select which one to keep.
    Never prints or inspects the file contents.
    """
    directory = private_dir or get_private_dir()
    matches = sorted(directory.glob("client_secret*.json"))

    if len(matches) == 0:
        raise FileNotFoundError(
            f"No Google Desktop OAuth client secret file matching 'client_secret*.json' "
            f"found in '{directory}'.\n"
            f"Please download your Desktop OAuth client secret JSON from Google Cloud Console "
            f"(APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app) "
            f"and place it directly in '{directory}'."
        )

    if len(matches) > 1:
        file_list = "\n  - ".join(m.name for m in matches)
        raise ValueError(
            f"Multiple client secret files matching 'client_secret*.json' found in '{directory}':\n"
            f"  - {file_list}\n"
            f"Please select which client secret to use by keeping only one client_secret*.json file "
            f"in '{directory}' and removing or renaming the others."
        )

    return matches[0]


def get_token_path(private_dir: Path | None = None) -> Path:
    """Return the absolute path to token.json inside GOOGLE_PRIVATE_DIR."""
    directory = private_dir or get_private_dir()
    return directory / TOKEN_FILENAME
