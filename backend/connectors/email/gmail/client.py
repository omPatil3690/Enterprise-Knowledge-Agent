"""
Gmail API Client.

Handles network I/O, OAuth 2.0 credential management, token refresh,
connection health verification, and message batch retrieval from the Gmail REST API (v1).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCRIPT_DIR = Path(__file__).resolve().parent
EMAIL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = EMAIL_DIR.parent.parent

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.drafts.readonly",
]


def find_default_credentials_file() -> Path:
    """Discovers credentials.json in common project paths."""
    candidates = [
        EMAIL_DIR / "credentials.json",
        SCRIPT_DIR / "credentials.json",
        SCRIPT_DIR / "tests" / "credentials.json",
        PROJECT_ROOT / "credentials.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return EMAIL_DIR / "credentials.json"


def find_default_token_file() -> Path:
    """Discovers token.json in common project paths."""
    candidates = [
        SCRIPT_DIR / "tests" / "token.json",
        SCRIPT_DIR / "token.json",
        EMAIL_DIR / "token.json",
        PROJECT_ROOT / "token.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return SCRIPT_DIR / "tests" / "token.json"


class GmailClient:
    """
    Client for interacting with the Google Gmail REST API v1.
    """

    def __init__(
        self,
        token_path: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize the Gmail client.
        
        Args:
            token_path: Path to stored user token.json (optional).
            credentials_path: Path to OAuth client credentials.json (optional).
        """
        self.token_file = Path(token_path) if token_path else find_default_token_file()
        self.creds_file = Path(credentials_path) if credentials_path else find_default_credentials_file()
        self._service: Optional[Resource] = None

    def get_credentials(self) -> Credentials:
        """Loads valid OAuth credentials, refreshing or launching browser flow if needed."""
        creds = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.creds_file.exists():
                    raise FileNotFoundError(
                        f"credentials.json not found at '{self.creds_file}'. "
                        "Please download OAuth client credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.creds_file), SCOPES)
                creds = flow.run_local_server(port=0)

            # Persist token for future headless execution
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "w", encoding="utf-8") as token_out:
                token_out.write(creds.to_json())

        return creds

    @property
    def service(self) -> Resource:
        """Returns the cached Google API Resource service object."""
        if self._service is None:
            creds = self.get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def test_connection(self) -> bool:
        """
        Tests whether the Gmail API credentials are valid by querying users.getProfile.
        
        Returns:
            True if authentication and API reachability succeed, False otherwise.
        """
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return bool(profile and "emailAddress" in profile)
        except Exception as e:
            print(f"⚠️ Gmail connection test failed: {e}")
            return False

    def list_messages(
        self,
        query: str = "",
        label_ids: Optional[List[str]] = None,
        max_results: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Queries message stubs from the user's mailbox matching search criteria.
        
        Args:
            query: Gmail search query string (e.g. 'after:2026/01/01', 'from:alice', 'is:unread').
            label_ids: Filter by Gmail labels (e.g. ['INBOX', 'IMPORTANT']).
            max_results: Max message IDs to return per page (up to 500).
            page_token: Cursor for pagination.

        Returns:
            Dictionary containing 'messages' list and optional 'nextPageToken'.
        """
        params: Dict[str, Any] = {"userId": "me", "maxResults": max_results}
        if query:
            params["q"] = query
        if label_ids:
            params["labelIds"] = label_ids
        if page_token:
            params["pageToken"] = page_token

        return self.service.users().messages().list(**params).execute()

    def get_message(self, message_id: str, format: str = "full") -> Dict[str, Any]:
        """
        Retrieves full details for a single email message.
        
        Args:
            message_id: Gmail message ID.
            format: 'full' (default, with MIME payload), 'metadata', 'minimal', or 'raw'.

        Returns:
            Raw message dictionary from Gmail API.
        """
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format=format)
            .execute()
        )

    def fetch_messages_batch(
        self,
        query: str = "",
        label_ids: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        High-level retrieval helper that paginates and retrieves full message payloads up to `limit`.
        
        Args:
            query: Optional search filter.
            label_ids: Optional label filter (defaults to None).
            limit: Maximum total full messages to retrieve.

        Returns:
            List of full raw Gmail message dictionaries.
        """
        all_messages: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while len(all_messages) < limit:
            batch_size = min(100, limit - len(all_messages))
            res = self.list_messages(
                query=query,
                label_ids=label_ids,
                max_results=batch_size,
                page_token=page_token,
            )
            stubs = res.get("messages", [])
            if not stubs:
                break

            for stub in stubs:
                msg_id = stub.get("id")
                if msg_id:
                    try:
                        full_msg = self.get_message(msg_id, format="full")
                        all_messages.append(full_msg)
                        if len(all_messages) >= limit:
                            break
                    except Exception as e:
                        print(f"⚠️ Warning: Could not retrieve Gmail message {msg_id}: {e}")

            page_token = res.get("nextPageToken")
            if not page_token:
                break

        return all_messages
