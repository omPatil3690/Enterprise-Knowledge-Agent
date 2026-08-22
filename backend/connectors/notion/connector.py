"""
Notion Connector Orchestrator.

Implements BaseConnector to provide a unified interface for:
- Testing Notion credentials and reachability
- Workspace auto-discovery of all accessible pages
- Single page loading by ID
- Full recursive hierarchy extraction and conversion to typed Document objects
- Incremental synchronization based on last edited timestamps
"""

import os
from typing import Any, Dict, List, Optional
from backend.connectors.base import BaseConnector
from backend.connectors.notion.client import NotionClient
from backend.connectors.notion.parser import normalize_page
from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata


def dict_to_content_block(data: Dict[str, Any], parent_id: Optional[str] = None) -> ContentBlock:
    """
    Recursively converts a normalized block dictionary into a typed ContentBlock object,
    preserving database schemas, columns, rows, and nested children.
    """
    block_type = BlockType.from_string(data.get("type", "unknown"))
    
    # Extract properties (checked status, language, heading level, total_rows, etc.)
    properties = {}
    if "checked" in data:
        properties["checked"] = data["checked"]
    if "language" in data:
        properties["language"] = data["language"]
    if "level" in data:
        properties["level"] = data["level"]
    if "total_rows" in data:
        properties["total_rows"] = data["total_rows"]

    raw_children = data.get("children", [])
    child_blocks = [dict_to_content_block(c, parent_id=data.get("block_id")) for c in raw_children]

    columns = data.get("columns", []) or data.get("headers", [])
    rows = data.get("rows", [])

    return ContentBlock(
        id=data.get("block_id", ""),
        type=block_type,
        text=data.get("text", ""),
        properties=properties,
        parent_id=parent_id,
        children=child_blocks,
        columns=columns,
        rows=rows,
    )


def dict_to_document(doc_dict: Dict[str, Any]) -> Document:
    """
    Converts a normalized dictionary (from parser.normalize_page) into a typed Document object.
    """
    metadata = DocumentMetadata(
        id=doc_dict.get("source_id", ""),
        title=doc_dict.get("title", "Untitled"),
        source_platform=doc_dict.get("source", "notion"),
        url=doc_dict.get("url"),
        created_time=doc_dict.get("created_at"),
        last_edited_time=doc_dict.get("updated_at"),
        parent_type=doc_dict.get("parent_type"),
        parent_id=str(doc_dict.get("parent_id")) if doc_dict.get("parent_id") is not None else None,
    )

    blocks: List[ContentBlock] = []
    for b_data in doc_dict.get("content", []):
        blocks.append(dict_to_content_block(b_data))

    return Document(metadata=metadata, blocks=blocks)


class NotionConnector(BaseConnector):
    """
    Enterprise Connector for Notion Workspaces and Pages.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        default_page_id: Optional[str] = None,
        notion_version: str = "2022-06-28",
    ):
        """
        Initialize the Notion Connector.

        Args:
            token: Notion integration API token (defaults to NOTION_TOKEN in .env).
            default_page_id: Optional default Page ID (defaults to NOTION_PAGE_ID in .env).
            notion_version: API version header string.
        """
        super().__init__(name="notion")
        self.default_page_id = default_page_id or os.getenv("NOTION_PAGE_ID")
        self.client = NotionClient(token=token, notion_version=notion_version)

    def test_connection(self) -> bool:
        """
        Validates API token credentials and connectivity.
        """
        return self.client.test_connection()

    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches, extracts, and normalizes a single Notion page into a typed Document.

        Args:
            doc_id: Notion page UUID.

        Returns:
            Typed Document object or None if failed.
        """
        try:
            full_data = self.client.retrieve_full_page(doc_id)
            page_data = full_data.get("page", {})
            blocks_data = full_data.get("blocks", [])

            if not page_data:
                return None

            normalized_dict = normalize_page(page_data, blocks_data)
            return dict_to_document(normalized_dict)
        except Exception as e:
            print(f"Error loading Notion document {doc_id}: {e}")
            return None

    def load_documents(self, auto_discover: bool = True) -> List[Document]:
        """
        Loads accessible documents from Notion.
        - If auto_discover is True, searches the entire workspace via POST /v1/search.
        - Otherwise, loads the default_page_id.

        Returns:
            List of typed Document objects ready for OKF conversion and chunking.
        """
        documents: List[Document] = []

        if auto_discover:
            try:
                pages = self.client.search_pages()
                for page in pages:
                    p_id = page.get("id")
                    if p_id:
                        doc = self.load_document_by_id(p_id)
                        if doc:
                            documents.append(doc)
            except Exception as e:
                print(f"Workspace auto-discovery search failed: {e}. Falling back to default page.")
                if self.default_page_id:
                    doc = self.load_document_by_id(self.default_page_id)
                    if doc:
                        documents.append(doc)
        elif self.default_page_id:
            doc = self.load_document_by_id(self.default_page_id)
            if doc:
                documents.append(doc)

        return documents

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only pages that were edited or created after `last_sync_time`.
        """
        if not last_sync_time:
            return self.load_documents()

        # In Notion, we can inspect search results' last_edited_time before pulling all blocks
        pages = self.client.search_pages()
        changed_docs: List[Document] = []

        for page in pages:
            edited = page.get("last_edited_time")
            if not edited or edited > last_sync_time:
                p_id = page.get("id")
                if p_id:
                    doc = self.load_document_by_id(p_id)
                    if doc:
                        changed_docs.append(doc)

        return changed_docs
