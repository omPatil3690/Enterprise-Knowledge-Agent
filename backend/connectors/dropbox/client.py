"""
Dropbox API Client.

Handles all network I/O with the Dropbox HTTP API v2, including:
- Credential validation and connection testing (/2/users/get_current_account)
- Folder listing & recursive walk (/2/files/list_folder)
- File metadata retrieval (/2/files/get_metadata)
- File content download (/2/files/download)
- Resilient error recovery for missing / inaccessible files
- Rate-limit handling (HTTP 429 with Retry-After semantics)
"""

import os
import time
from typing import Any, Dict, List, Optional
import requests

# Dropbox API endpoints
DROPBOX_API_BASE = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_BASE = "https://content.dropboxapi.com/2"


class DropboxClient:
    """
    Client for interacting with the Dropbox API v2.
    Uses an OAuth 2.0 access token (DROPBOX_TOKEN) for authentication.
    Implemented directly over Http/JSON (no third-party SDK required).
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the Dropbox client.

        Args:
            token: Dropbox access token (defaults to DROPBOX_TOKEN env var).
        """
        self.token = token or os.getenv("DROPBOX_TOKEN")
        if not self.token:
            raise ValueError(
                "Dropbox token must be provided or set in DROPBOX_TOKEN environment variable."
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Sleeps when Dropbox reports a rate limit (HTTP 429).
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            delay = 2
            if retry_after:
                try:
                    delay = max(1, int(retry_after))
                except ValueError:
                    pass
            print(f"    ⏳ Dropbox rate limit hit. Sleeping {delay}s...")
            time.sleep(delay)

    def _post(self, endpoint: str, body: Dict[str, Any]) -> Optional[requests.Response]:
        """
        Posts to a JSON endpoint on api.dropboxapi.com with 429 retry handling.

        Returns:
            Response object (caller inspects status), or the last response.
        """
        url = f"{DROPBOX_API_BASE}/{endpoint}"
        last = None
        for _ in range(3):
            last = self.session.post(url, json=body)
            if last.status_code == 429:
                self._handle_rate_limit(last)
                continue
            break
        return last

    def test_connection(self) -> bool:
        """
        Validates the token and API reachability against /2/users/get_current_account.

        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        try:
            response = self._post("users/get_current_account", {})
            return bool(response and response.status_code == 200)
        except Exception:
            return False

    def get_current_account(self) -> Optional[Dict[str, Any]]:
        """
        Returns the metadata of the authenticated account.
        """
        response = self._post("users/get_current_account", {})
        if response and response.status_code == 200:
            return response.json()
        return None

    def list_folder(
        self,
        path: str = "",
        recursive: bool = True,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Lists folders and files under a given Dropbox path, using cursor pagination.

        Args:
            path: Dropbox path (root = '' or '/').
            recursive: If True, lists all descendants recursively via the API.
            limit: Maximum entries per page.

        Returns:
            List of Dropbox metadata entries (FileMetadata / FolderMetadata).
        """
        entries: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            body: Dict[str, Any] = {"path": path or "", "recursive": recursive, "limit": limit}
            endpoint = "files/list_folder"
            if cursor:
                endpoint = "files/list_folder/continue"
                body = {"cursor": cursor}

            response = self._post(endpoint, body)
            if not response or response.status_code != 200:
                break

            data = response.json()
            entries.extend(data.get("entries", []))

            if not data.get("has_more"):
                break
            cursor = data.get("cursor")

            # Guard against infinite loops
            if len(entries) > 100000:
                break

        return entries

    def get_file_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a single file or folder's metadata.

        Args:
            path: Dropbox path.

        Returns:
            Metadata dictionary, or None if not found / inaccessible.
        """
        response = self._post("files/get_metadata", {"path": path})
        if response and response.status_code == 200:
            return response.json()
        return None

    def download_file(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Downloads a text file's content from Dropbox.

        Args:
            path: Dropbox path to the file.

        Returns:
            Dict with 'name', 'path_lower', 'server_modified', and decoded 'content',
            or None on failure/binary.
        """
        url = f"{DROPBOX_CONTENT_BASE}/files/download"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Dropbox-API-Arg": __import__("json").dumps({"path": path}),
        }
        try:
            response = self.session.post(url, headers=headers)
            if response.status_code == 429:
                self._handle_rate_limit(response)
                response = self.session.post(url, headers=headers)
            if response.status_code != 200:
                return None

            result_str = response.headers.get("Dropbox-API-Result")
            if not result_str:
                return None

            import json as _json
            meta = _json.loads(result_str)

            content = response.content.decode("utf-8", errors="replace")
            return {
                "name": meta.get("name"),
                "path_lower": meta.get("path_lower"),
                "server_modified": meta.get("server_modified"),
                "size": meta.get("size"),
                "content": content,
            }
        except Exception:
            return None
