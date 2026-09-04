"""Shared Google auth for Brain scripts."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BRAIN_CONFIG = Path.home() / ".config" / "brain"
TOKEN_FILE = BRAIN_CONFIG / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def get_credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            f"Google token not found at {TOKEN_FILE}. "
            "Re-authenticate via `gws auth login` and copy the token, or run the Brain setup script."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def docs_service():
    return build("docs", "v1", credentials=get_credentials())


def drive_service():
    return build("drive", "v3", credentials=get_credentials())


def sheets_service():
    return build("sheets", "v4", credentials=get_credentials())
