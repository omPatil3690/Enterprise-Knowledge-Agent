"""
Notion API Client.

Handles all network I/O with the Notion API, including:
- Credential validation and connection testing (/v1/users/me)
- Workspace auto-discovery and page search (/v1/search)
- Page metadata retrieval (/v1/pages/{id})
- Cursor-based pagination (has_more / next_cursor)
- Recursive child block retrieval for nested structures (toggles, lists, callouts)
- Child database row querying (/v1/databases/{id}/query) with resilient error recovery
"""

import os
import time
from typing import Any, Dict, List, Optional
import requests


def format_uuid(val: str) -> str:
    """Ensures UUID is formatted with standard hyphens (8-4-4-4-12) as expected by Notion API."""
    clean = val.replace("-", "").strip()
    if len(clean) == 32:
        return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"
    return val


class NotionClient:
    """
    Client for interacting with the Notion REST API.
    """
    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, token: Optional[str] = None, notion_version: str = "2022-06-28"):
        """
        Initialize the Notion client.
        
        Args:
            token: Notion integration API token (defaults to NOTION_TOKEN env var).
            notion_version: API version string.
        """
        self.token = token or os.getenv("NOTION_TOKEN")
        if not self.token:
            raise ValueError("Notion token must be provided or set in NOTION_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def test_connection(self) -> bool:
        """
        Validates API token credentials and API reachability against /v1/users/me.
        
        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        url = f"{self.BASE_URL}/users/me"
        try:
            response = self.session.get(url)
            return response.status_code == 200
        except Exception:
            return False

    def search_pages(
        self,
        query: str = "",
        filter_object: Optional[str] = None,
        sort_by_edited: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Discovers all accessible pages and data sources in the workspace using POST /v1/search.
        If filter_object is None (default), returns all shared pages, wikis, and databases.
        
        Args:
            query: Optional search text to filter page titles. If empty, returns all shared objects.
            filter_object: 'page', 'data_source', 'database', or None (returns everything).
            sort_by_edited: If True, sorts by last_edited_time descending.

        Returns:
            List of page / database object dictionaries.
        """
        url = f"{self.BASE_URL}/search"
        pages: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            body: Dict[str, Any] = {"page_size": 100}

            if filter_object:
                body["filter"] = {"value": filter_object, "property": "object"}

            if sort_by_edited:
                body["sort"] = {
                    "direction": "descending",
                    "timestamp": "last_edited_time"
                }

            if query:
                body["query"] = query

            if cursor:
                body["start_cursor"] = cursor

            response = self.session.post(url, json=body)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                continue
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            pages.extend(results)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return pages

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Fetches metadata for a given page or database ID.
        Tries /pages/{id} -> /databases/{id} -> /blocks/{id}.
        """
        formatted_id = format_uuid(page_id)
        url = f"{self.BASE_URL}/pages/{formatted_id}"
        
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        
        # Fallback to /databases/ endpoint if it's a root database
        db_url = f"{self.BASE_URL}/databases/{formatted_id}"
        db_response = self.session.get(db_url)
        if db_response.status_code == 200:
            return db_response.json()

        # Fallback to /blocks/ endpoint if /pages/ failed
        block_url = f"{self.BASE_URL}/blocks/{formatted_id}"
        block_response = self.session.get(block_url)
        if block_response.status_code == 200:
            return block_response.json()
        
        response.raise_for_status()
        return {}

    def fetch_database_rows(self, database_id: str) -> List[Dict[str, Any]]:
        """
        Queries all rows/items inside a Notion child_database via POST /v1/databases/{id}/query.
        Handles cursor pagination with resilient error recovery.
        """
        formatted_id = format_uuid(database_id)
        url = f"{self.BASE_URL}/databases/{formatted_id}/query"
        rows: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            body: Dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor

            try:
                response = self.session.post(url, json=body)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    time.sleep(retry_after)
                    continue

                if response.status_code != 200:
                    try:
                        err_msg = response.json().get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    print(f"    ⚠️ Notice: Could not query database rows for {formatted_id} ({response.status_code}: {err_msg})")
                    break

                data = response.json()
                results = data.get("results", [])
                rows.extend(results)

                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
            except Exception as e:
                print(f"    ⚠️ Notice: Database query skipped for {formatted_id}: {e}")
                break

        return rows

    def fetch_all_blocks(
        self,
        block_id: str,
        fetch_nested: bool = True,
        fetch_db_rows: bool = True,
        max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all child blocks for a given block/page ID, handling:
        1. Pagination (looping via start_cursor while has_more == True)
        2. Nested block hierarchies (recursively fetching children when has_children == True)
        3. Database rows (querying database items when type == 'child_database')

        Args:
            block_id: The ID of the parent block or page.
            fetch_nested: If True, recursively fetch children of nested blocks (toggles, lists).
            fetch_db_rows: If True, query database rows for child_database blocks.
            max_depth: Maximum recursion depth to prevent infinite loops.

        Returns:
            List of raw Notion block dictionaries, with nested children/rows attached.
        """
        formatted_id = format_uuid(block_id)
        url = f"{self.BASE_URL}/blocks/{formatted_id}/children"
        
        all_blocks: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            params: Dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            response = self.session.get(url, params=params)
            
            # Simple rate-limit handling (HTTP 429)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            for block in results:
                b_type = block.get("type")
                b_id = block.get("id")
                has_children = block.get("has_children", False)

                # 1. Expand Database rows (e.g. Todo List database)
                if fetch_db_rows and b_type == "child_database" and b_id:
                    db_rows = self.fetch_database_rows(b_id)
                    block["database_rows"] = db_rows

                # 2. Recurse for toggles, lists, callouts, quotes (excluding separate child_pages)
                elif fetch_nested and has_children and b_type != "child_page" and max_depth > 0 and b_id:
                    block["children"] = self.fetch_all_blocks(
                        block_id=b_id,
                        fetch_nested=True,
                        fetch_db_rows=fetch_db_rows,
                        max_depth=max_depth - 1
                    )
                else:
                    block["children"] = []

                all_blocks.append(block)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return all_blocks

    def retrieve_full_page(self, page_id: str) -> Dict[str, Any]:
        """
        High-level retrieval function that pulls both page metadata and the full block tree.
        
        Returns:
            Dict containing 'page' metadata JSON and 'blocks' tree JSON.
        """
        page_data = self.get_page(page_id)
        blocks_data = self.fetch_all_blocks(page_id, fetch_nested=True, fetch_db_rows=True)
        
        return {
            "page": page_data,
            "blocks": blocks_data
        }
