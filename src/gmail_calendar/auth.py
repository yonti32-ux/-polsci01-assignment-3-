"""Authentication and credential management for Google APIs.

Handles OAuth 2.0 authorization flow, token validation, account verification,
and diagnostic logging to stderr. Stdout is strictly reserved for MCP messages.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gmail_calendar.config import (
    ENV_CLASS_EMAIL_KEY,
    SCOPES,
    find_client_secret,
    get_private_dir,
    get_token_path,
)


def log_stderr(message: str) -> None:
    """Print diagnostic messages strictly to stderr so stdout remains clean."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def get_authorized_email(creds: Credentials) -> str:
    """Fetch the authenticated user's email address using the Gmail API."""
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "").strip()
    if not email:
        raise ValueError("Could not determine email address from Google account profile.")
    return email


def load_credentials(expected_email: str | None = None) -> Credentials:
    """Load and validate credentials from token.json in GOOGLE_PRIVATE_DIR.

    Raises:
        FileNotFoundError: If token.json is missing with instructions to run auth.
        ValueError: If scopes are insufficient or email does not match expected_email.
    """
    private_dir = get_private_dir()
    token_path = get_token_path(private_dir)

    if not token_path.is_file():
        msg = (
            f"Google OAuth token not found at '{token_path}'.\n"
            f"Please run the manual authorization command first:\n"
            f"  uv run auth --expected-email <your-class-email>"
        )
        log_stderr(f"[Auth Error] {msg}")
        raise FileNotFoundError(msg)

    try:
        # Load token without passing scopes override so creds.scopes reflects actual granted scopes
        creds = Credentials.from_authorized_user_file(str(token_path))
    except Exception as err:
        msg = f"Failed to read token from '{token_path}': {err}"
        log_stderr(f"[Auth Error] {msg}")
        raise ValueError(msg) from err

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            log_stderr("Refreshing expired Google OAuth access token...")
            creds.refresh(Request())
            # Save refreshed token back to token.json
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as err:
            msg = f"Failed to refresh expired token at '{token_path}': {err}. Please re-authorize."
            log_stderr(f"[Auth Error] {msg}")
            raise ValueError(msg) from err

    if not creds or not creds.valid:
        msg = f"Credentials at '{token_path}' are invalid. Please run the authorization command."
        log_stderr(f"[Auth Error] {msg}")
        raise ValueError(msg)

    # Verify scopes
    if not creds.has_scopes(SCOPES):
        msg = (
            f"Token at '{token_path}' lacks required permissions.\n"
            f"Required scopes: {SCOPES}\n"
            f"Granted scopes: {creds.scopes}\n"
            f"Please re-authorize with: uv run auth --expected-email <your-class-email> --overwrite"
        )
        log_stderr(f"[Auth Error] {msg}")
        raise ValueError(msg)

    # Verify account against expected email if provided (or via environment variable)
    target_email = expected_email or os.environ.get(ENV_CLASS_EMAIL_KEY)
    if target_email:
        target_email = target_email.strip().lower()
        actual_email = get_authorized_email(creds).lower()
        if actual_email != target_email:
            msg = (
                f"Account mismatch: Token at '{token_path}' belongs to '{actual_email}', "
                f"but expected class account is '{target_email}'.\n"
                f"Please re-authorize with: uv run auth --expected-email {target_email} --overwrite"
            )
            log_stderr(f"[Auth Error] {msg}")
            raise ValueError(msg)

    return creds


def run_interactive_oauth(
    expected_email: str,
    overwrite: bool = False,
    private_dir: Path | None = None,
) -> Path:
    """Run interactive OAuth in browser to authorize class account and save token.json.

    - Forces account selection via prompt='select_account'.
    - Verifies the authorized Gmail address against expected_email BEFORE saving.
    - Never silently overwrites an existing token unless overwrite=True is explicitly given.
    - Diagnostic output is sent to stderr.
    """
    directory = private_dir or get_private_dir()
    token_path = get_token_path(directory)
    client_secret_path = find_client_secret(directory)

    target_email = expected_email.strip().lower()
    if not target_email or "@" not in target_email:
        raise ValueError(f"Invalid expected class email: '{expected_email}'")

    # Check for existing token
    if token_path.exists() and not overwrite:
        # Check if existing token already matches target_email
        try:
            existing_creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if existing_creds.valid or existing_creds.refresh_token:
                if existing_creds.expired and existing_creds.refresh_token:
                    existing_creds.refresh(Request())
                existing_email = get_authorized_email(existing_creds).lower()
                if existing_email == target_email and existing_creds.has_scopes(SCOPES):
                    log_stderr(
                        f"Existing token at '{token_path}' is already valid for '{target_email}'.\n"
                        f"No action needed. To force re-authorization, run with --overwrite."
                    )
                    return token_path
        except Exception:
            pass

        msg = (
            f"Token file already exists at '{token_path}'.\n"
            f"To prevent silently overwriting an existing token, authorization was stopped.\n"
            f"If you wish to replace it, pass --overwrite or remove '{token_path}' manually."
        )
        log_stderr(f"[Auth Error] {msg}")
        raise FileExistsError(msg)

    log_stderr("=" * 60)
    log_stderr("Google OAuth Class Account Authorization")
    log_stderr(f"Expected class account : {target_email}")
    log_stderr(f"Private directory      : {directory}")
    log_stderr(f"Client secret file     : {client_secret_path.name}")
    log_stderr("Opening browser for authorization. Please select your class account.")
    log_stderr("=" * 60)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path),
        scopes=SCOPES,
    )

    # prompt="select_account" forces account chooser; access_type="offline" ensures refresh token
    creds = flow.run_local_server(
        port=0,
        prompt="select_account",
        access_type="offline",
        authorization_prompt_message="Please visit this URL to authorize your class account:\n{url}\n",
        success_message=(
            "Authorization completed! You may close this browser tab and return to the terminal."
        ),
    )

    # Verify authorized email against expected_email
    log_stderr("Verifying authorized Google account identity...")
    actual_email = get_authorized_email(creds).strip().lower()

    if actual_email != target_email:
        msg = (
            f"Account mismatch!\n"
            f"You logged in as: '{actual_email}'\n"
            f"Expected account: '{target_email}'\n\n"
            f"The token will NOT be saved to protect your credentials. "
            f"Please run the authorization command again and select '{target_email}' in the browser."
        )
        log_stderr(f"[Auth Error] {msg}")
        raise ValueError(msg)

    # Save token directly to GOOGLE_PRIVATE_DIR
    token_path.write_text(creds.to_json(), encoding="utf-8")
    log_stderr(f"SUCCESS: Token verified for '{actual_email}' and saved to:")
    log_stderr(f"  {token_path}")
    return token_path


def main() -> None:
    """CLI entry point for manual authorization: uv run auth --expected-email <email>."""
    parser = argparse.ArgumentParser(
        description="Authorize Google account for class project and save token directly in GOOGLE_PRIVATE_DIR.",
    )
    parser.add_argument(
        "--expected-email",
        "-e",
        type=str,
        default=os.environ.get(ENV_CLASS_EMAIL_KEY, ""),
        help="Expected class Gmail address (e.g. student@gmail.com).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing token.json if present.",
    )

    args = parser.parse_args()

    expected_email = args.expected_email.strip()
    if not expected_email:
        # Prompt user if not provided via CLI or environment
        try:
            sys.stderr.write("Enter your expected class Gmail address: ")
            sys.stderr.flush()
            expected_email = input().strip()
        except (EOFError, KeyboardInterrupt):
            log_stderr("\nAuthorization cancelled by user.")
            sys.exit(1)

    if not expected_email:
        log_stderr("Error: Expected class email address is required.")
        sys.exit(1)

    try:
        run_interactive_oauth(expected_email=expected_email, overwrite=args.overwrite)
        sys.exit(0)
    except Exception as err:
        log_stderr(f"\nAuthorization failed: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
