"""
Dropbox API Client using official Dropbox Python SDK.

Handles all network I/O with Dropbox using dropbox.Dropbox:
- Credential management (Access Token & OAuth 2.0 Refresh Token auto-refresh)
- Account verification and connection testing (users_get_current_account)
- Folder listing & recursive walk with cursor pagination (files_list_folder & files_list_folder_continue)
- File metadata retrieval (files_get_metadata)
- File content download (files_download)
- Resilient error recovery and rate-limit handling (RateLimitError, AuthError)
"""

import os
from typing import Any, Dict, List, Optional
import dotenv

import dropbox
from dropbox.exceptions import AuthError, BadInputError, RateLimitError
from dropbox.files import FileMetadata, FolderMetadata

dotenv.load_dotenv()


class DropboxClient:
    """
    Client for interacting with Dropbox via the official Dropbox Python SDK.
    Supports both short-lived access tokens and permanent OAuth 2.0 refresh tokens.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        """
        Initialize the Dropbox client.
        
        Prioritizes Refresh Token if available for automatic background token renewal.
        """
        self.app_key = app_key or os.getenv("DROPBOX_APP_KEY")
        self.app_secret = app_secret or os.getenv("DROPBOX_APP_SECRET")
        self.refresh_token = refresh_token or os.getenv("DROPBOX_REFRESH_TOKEN")
        self.token = token or os.getenv("DROPBOX_ACCESS_TOKEN") or os.getenv("DROPBOX_TOKEN")

        if self.app_key and self.app_secret and self.refresh_token:
            self._dbx = dropbox.Dropbox(
                app_key=self.app_key,
                app_secret=self.app_secret,
                oauth2_refresh_token=self.refresh_token,
            )
        elif self.token:
            self._dbx = dropbox.Dropbox(self.token)
        else:
            raise ValueError(
                "Dropbox credentials missing: Provide DROPBOX_REFRESH_TOKEN (with APP_KEY/SECRET) "
                "or DROPBOX_ACCESS_TOKEN in .env."
            )

    @property
    def dbx(self) -> dropbox.Dropbox:
        """Returns the active Dropbox SDK instance."""
        return self._dbx

    def test_connection(self) -> bool:
        """
        Validates credentials and API reachability by querying users_get_current_account.
        
        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        try:
            account = self.dbx.users_get_current_account()
            return bool(account and account.account_id)
        except Exception as e:
            print(f"⚠️ Dropbox connection test failed: {e}")
            return False

    def get_current_account(self) -> Optional[Dict[str, Any]]:
        """
        Returns the metadata dictionary of the authenticated account.
        """
        try:
            acc = self.dbx.users_get_current_account()
            return {
                "account_id": acc.account_id,
                "display_name": acc.name.display_name,
                "email": acc.email,
                "country": acc.country,
            }
        except Exception as e:
            print(f"⚠️ Could not fetch account info: {e}")
            return None

    def list_folder(
        self,
        path: str = "",
        recursive: bool = True,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Lists folders and files under a given Dropbox path using SDK cursor pagination.
        
        Args:
            path: Dropbox path (root = '' or '/').
            recursive: If True, recursively lists all subfolders and files.
            limit: Maximum entries per API page request.

        Returns:
            List of normalized dictionary entries.
        """
        entries: List[Dict[str, Any]] = []
        clean_path = "" if path in ("/", "\\") else path

        try:
            res = self.dbx.files_list_folder(
                path=clean_path,
                recursive=recursive,
                limit=min(limit, 2000),
            )

            while True:
                for entry in res.entries:
                    entries.append(self._entry_to_dict(entry))

                if not res.has_more:
                    break

                res = self.dbx.files_list_folder_continue(res.cursor)

                if len(entries) > 100000:
                    break

        except (AuthError, BadInputError, RateLimitError) as e:
            print(f"⚠️ Error listing folder '{clean_path}': {e}")
        except Exception as e:
            print(f"⚠️ Unexpected error listing folder '{clean_path}': {e}")

        return entries

    def get_file_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a single file or folder.
        
        Args:
            path: Dropbox file or folder path.

        Returns:
            Metadata dictionary, or None if not found / inaccessible.
        """
        try:
            meta = self.dbx.files_get_metadata(path)
            return self._entry_to_dict(meta)
        except Exception as e:
            print(f"⚠️ Could not get metadata for '{path}': {e}")
            return None

    def download_file(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Downloads a file's content from Dropbox.
        
        Args:
            path: Dropbox path to the file.

        Returns:
            Dictionary with name, path_lower, server_modified, size, and decoded text content,
            or None on failure.
        """
        try:
            metadata, response = self.dbx.files_download(path)
            # Decode content assuming UTF-8 with latin-1 fallback
            raw_bytes = response.content
            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_bytes.decode("latin-1", errors="replace")

            return {
                "name": metadata.name,
                "path_lower": metadata.path_lower,
                "path_display": metadata.path_display,
                "server_modified": metadata.server_modified.isoformat() if metadata.server_modified else None,
                "client_modified": metadata.client_modified.isoformat() if metadata.client_modified else None,
                "size": metadata.size,
                "id": metadata.id,
                "rev": metadata.rev,
                "content": content,
            }
        except Exception as e:
            print(f"⚠️ Could not download file '{path}': {e}")
            return None

    @staticmethod
    def _entry_to_dict(entry: Any) -> Dict[str, Any]:
        """Converts an SDK FileMetadata or FolderMetadata object into a dictionary."""
        is_file = isinstance(entry, FileMetadata)
        is_folder = isinstance(entry, FolderMetadata)

        tag = "file" if is_file else ("folder" if is_folder else "deleted")

        data: Dict[str, Any] = {
            ".tag": tag,
            "name": getattr(entry, "name", ""),
            "path_lower": getattr(entry, "path_lower", ""),
            "path_display": getattr(entry, "path_display", ""),
            "id": getattr(entry, "id", None),
        }

        if is_file:
            data["size"] = getattr(entry, "size", 0)
            data["rev"] = getattr(entry, "rev", None)
            server_mod = getattr(entry, "server_modified", None)
            client_mod = getattr(entry, "client_modified", None)
            data["server_modified"] = server_mod.isoformat() if server_mod else None
            data["client_modified"] = client_mod.isoformat() if client_mod else None

        return data
