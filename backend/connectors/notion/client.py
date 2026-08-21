"""
Notion API Client.

Handles all network I/O with the Notion API, including:
- Page retrieval
- Cursor-based pagination (has_more / next_cursor)
- Recursive child block retrieval for nested structures (toggles, lists, callouts)
"""

import os
import time
from typing import Any, Dict, List, Optional
import requests


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

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Fetches page-level metadata for a given page ID.
        Tries /pages/{id} first, with fallback to /blocks/{id}.
        """
        clean_id = page_id.replace("-", "")
        url = f"{self.BASE_URL}/pages/{clean_id}"
        
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        
        # Fallback to block endpoint if /pages/ failed (e.g. for some workspace root blocks)
        block_url = f"{self.BASE_URL}/blocks/{clean_id}"
        block_response = self.session.get(block_url)
        if block_response.status_code == 200:
            return block_response.json()
        
        response.raise_for_status()
        return {}

    def fetch_all_blocks(
        self,
        block_id: str,
        fetch_nested: bool = True,
        max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all child blocks for a given block/page ID, handling both:
        1. Pagination (looping via start_cursor while has_more == True)
        2. Nested block hierarchies (recursively fetching children when has_children == True)

        Args:
            block_id: The ID of the parent block or page.
            fetch_nested: If True, recursively fetch children of nested blocks (toggles, lists).
            max_depth: Maximum recursion depth to prevent infinite loops.

        Returns:
            List of raw Notion block dictionaries, with nested children attached under 'children'.
        """
        clean_id = block_id.replace("-", "")
        url = f"{self.BASE_URL}/blocks/{clean_id}/children"
        
        all_blocks: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        # 1. Handle Cursor-Based Pagination
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

            # 2. Handle Nested Children Recursion
            for block in results:
                b_type = block.get("type")
                has_children = block.get("has_children", False)

                # Fetch nested children for structural blocks (toggles, lists, callouts, quotes)
                # Note: We do NOT recurse into 'child_page' here because child pages are separate documents
                if fetch_nested and has_children and b_type != "child_page" and max_depth > 0:
                    child_id = block.get("id")
                    if child_id:
                        block["children"] = self.fetch_all_blocks(
                            block_id=child_id,
                            fetch_nested=True,
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
        blocks_data = self.fetch_all_blocks(page_id, fetch_nested=True)
        
        return {
            "page": page_data,
            "blocks": blocks_data
        }
