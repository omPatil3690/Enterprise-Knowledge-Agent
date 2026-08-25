"""
Gmail API Test & Payload Extractor.

Authenticates via OAuth 2.0 (gmail.readonly) and exports inbox messages
and raw message payloads to test_data/ as JSON files rather than printing to terminal.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Setup paths relative to script location
SCRIPT_DIR = Path(__file__).resolve().parent
GMAIL_DIR = SCRIPT_DIR.parent
EMAIL_DIR = GMAIL_DIR.parent
PROJECT_ROOT = EMAIL_DIR.parent.parent

TEST_DATA_DIR = GMAIL_DIR / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.drafts.readonly",
]


def find_credentials_file() -> Path:
    """Finds credentials.json in common project locations."""
    candidates = [
        EMAIL_DIR / "credentials.json",
        GMAIL_DIR / "credentials.json",
        SCRIPT_DIR / "credentials.json",
        PROJECT_ROOT / "credentials.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return EMAIL_DIR / "credentials.json"


def authenticate_gmail(token_path: Optional[Path] = None, credentials_path: Optional[Path] = None) -> Credentials:
    """
    Authenticates or refreshes OAuth 2.0 credentials for Gmail.
    Stores and reuses token.json.
    """
    token_file = token_path or (SCRIPT_DIR / "token.json")
    creds_file = credentials_path or find_credentials_file()

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_file.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {creds_file}. "
                    "Please download OAuth client credentials from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future headless runs
        with open(token_file, "w", encoding="utf-8") as token_out:
            token_out.write(creds.to_json())

    return creds


def main():
    print("📡 Authenticating with Gmail API (OAuth 2.0)...")
    creds = authenticate_gmail()
    print("✅ Authentication successful!")

    service = build("gmail", "v1", credentials=creds)

    # 1. Fetch message IDs from inbox
    print("📥 Querying inbox messages (maxResults=5)...")
    list_results = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=5)
        .execute()
    )

    messages = list_results.get("messages", [])
    if not messages:
        print("⚠️ No messages found in INBOX.")
        return

    # Save list results to test_data/inbox_messages_list.json
    list_out_file = TEST_DATA_DIR / "inbox_messages_list.json"
    with open(list_out_file, "w", encoding="utf-8") as f:
        json.dump(list_results, f, indent=2, ensure_ascii=False)

    # 2. Fetch full payload for each message
    print(f"📦 Retrieving full payloads for {len(messages)} message(s)...")
    all_messages_data = []

    for idx, msg_stub in enumerate(messages, 1):
        m_id = msg_stub["id"]
        full_msg = (
            service.users()
            .messages()
            .get(userId="me", id=m_id, format="full")
            .execute()
        )
        all_messages_data.append(full_msg)

        # Save individual message JSON
        single_msg_file = TEST_DATA_DIR / f"message_{m_id}.json"
        with open(single_msg_file, "w", encoding="utf-8") as f:
            json.dump(full_msg, f, indent=2, ensure_ascii=False)

    # Save aggregated messages JSON
    all_out_file = TEST_DATA_DIR / "all_sample_messages.json"
    with open(all_out_file, "w", encoding="utf-8") as f:
        json.dump(all_messages_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("🎉 All Gmail payloads successfully saved to test_data/ (no terminal dump):")
    print(f"   • List Index:  {list_out_file.relative_to(PROJECT_ROOT)}")
    print(f"   • Full Batch:  {all_out_file.relative_to(PROJECT_ROOT)}")
    print(f"   • Directory:   {TEST_DATA_DIR.relative_to(PROJECT_ROOT)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()