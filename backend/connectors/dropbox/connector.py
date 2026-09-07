"""
Dropbox Connector Orchestrator.

Implements BaseConnector to provide a unified interface for:
- Testing Dropbox credentials and reachability
- Folder/file listing and recursive walk
- Single file/folder loading by ID or path
- Text file content ingestion into typed Document objects
- Incremental synchronization based on modified timestamps
"""

import os
from typing import Any, Dict, List, Optional

from backend.connectors.base import BaseConnector
from backend.connectors.dropbox.client import DropboxClient
from backend.connectors.dropbox.parser import (
    is_text_file,
    normalize_file_document,
    normalize_folder_document,
)
from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata
from backend.models.dropbox import DropboxFile, DropboxFolder


def dict_to_content_block(data: Dict[str, Any], parent_id: Optional[str] = None) -> ContentBlock:
    """
    Recursively converts a normalized block dictionary into a typed ContentBlock object.
    """
    block_type = BlockType.from_string(data.get("type", "unknown"))

    properties: Dict[str, Any] = {}
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
    Converts a normalized dictionary (from parser functions) into a typed Document object.
    """
    metadata = DocumentMetadata(
        id=doc_dict.get("source_id", ""),
        title=doc_dict.get("title", "Untitled"),
        source_platform=doc_dict.get("source", "dropbox"),
        url=doc_dict.get("url"),
        created_time=doc_dict.get("created_at"),
        last_edited_time=doc_dict.get("updated_at"),
        created_by=doc_dict.get("created_by"),
        last_edited_by=doc_dict.get("last_edited_by"),
        parent_type=doc_dict.get("parent_type"),
        parent_id=str(doc_dict.get("parent_id")) if doc_dict.get("parent_id") is not None else None,
        extra=doc_dict.get("extra", {}),
    )

    blocks: List[ContentBlock] = []
    for b_data in doc_dict.get("content", []):
        blocks.append(dict_to_content_block(b_data))

    return Document(metadata=metadata, blocks=blocks)


class DropboxConnector(BaseConnector):
    """
    Enterprise Connector for Dropbox files and folders.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        root_path: str = "",
        include_folders: bool = True,
        include_files: bool = True,
        max_files: int = 200,
    ):
        """
        Initialize the Dropbox Connector.

        Args:
            token: Dropbox access token (defaults to DROPBOX_TOKEN in .env).
            root_path: Dropbox root path to walk (default '' = whole account).
            include_folders: If True, produces folder Documents with child tables.
            include_files: If True, downloads and ingests text files.
            max_files: Maximum number of files to download during load_documents.
        """
        super().__init__(name="dropbox")
        self.root_path = root_path or ""
        self.include_folders = include_folders
        self.include_files = include_files
        self.max_files = max_files
        self.client = DropboxClient(token=token)

    def test_connection(self) -> bool:
        """Validates Dropbox token credentials and API reachability."""
        return self.client.test_connection()

    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches and normalizes a single Dropbox resource by path or ID.

        Args:
            doc_id: Dropbox path (e.g. '/folder/file.txt') or resource ID.

        Returns:
            Typed Document object or None if failed / binary.
        """
        try:
            if doc_id.startswith("id:"):
                # metadata lookup by id requires ListFolderGetMetadataArg; keep simple:
                return None

            meta = self.client.get_file_metadata(doc_id)
            if not meta:
                print(f"⚠️ Dropbox resource {doc_id} not found or inaccessible.")
                return None

            if meta.get(".tag") == "folder":
                children = self.client.list_folder(path=doc_id, recursive=False)
                folder = DropboxFolder.from_api(meta, children=children)
                return folder.to_intermediate_document()

            # File
            if not is_text_file((meta.get("path_lower") or doc_id)):
                print(f"⚠️ Skipping binary/non-text file: {doc_id}")
                return None
            downloaded = self.client.download_file(doc_id) or {}
            content = downloaded.get("content")
            raw_bytes = downloaded.get("raw_bytes")
            file_doc = DropboxFile.from_api(meta, content=content, raw_bytes=raw_bytes)
            return file_doc.to_intermediate_document()
        except Exception as e:
            print(f"⚠️ Error loading Dropbox resource {doc_id}: {e}")
            return None

    def load_documents(self) -> List[Document]:
        """
        Loads documents from Dropbox by walking the configured root path.

        Returns:
            List of typed Document objects ready for OKF conversion and chunking.
        """
        documents: List[Document] = []

        print(f"📂 Listing Dropbox folder: '{self.root_path or '/'}'...")
        entries = self.client.list_folder(path=self.root_path, recursive=True)
        if not entries:
            print("⚠️ No entries found.")
            return documents

        print(f"📑 Found {len(entries)} item(s) in the Dropbox account.")
        print("-" * 60)

        if self.include_folders:
            for entry in entries:
                if entry.get(".tag") != "folder":
                    continue
                folder_doc = self._build_folder_document(entry)
                if folder_doc:
                    documents.append(folder_doc)

        file_entries = [e for e in entries if e.get(".tag") == "file"]
        downloaded = 0
        for entry in file_entries:
            if downloaded >= self.max_files:
                print(f"🔒 Reached max_files limit ({self.max_files}). Skipping remaining files.")
                break
            if not self.include_files:
                break
            path = entry.get("path_lower") or entry.get("path_display")
            if not path or not is_text_file(path):
                continue
            try:
                downloaded_file = self.client.download_file(path) or {}
                content = downloaded_file.get("content")
                raw_bytes = downloaded_file.get("raw_bytes")
                file_doc = DropboxFile.from_api(entry, content=content, raw_bytes=raw_bytes)
                documents.append(file_doc.to_intermediate_document())
                downloaded += 1
            except Exception as e:
                print(f"⚠️ Error downloading {path}: {e}")

        return documents

    def _build_folder_document(self, entry: Dict[str, Any]) -> Optional[Document]:
        """
        Builds a folder Document with an immediate-children table (not recursively fetched).
        """
        try:
            path = entry.get("path_lower") or entry.get("path_display") or ""
            children = self.client.list_folder(path=path, recursive=False)
            folder = DropboxFolder.from_api(entry, children=children)
            return folder.to_intermediate_document()
        except Exception as e:
            print(f"⚠️ Error building folder document: {e}")
            return None

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only files/folders modified after `last_sync_time`.

        Args:
            last_sync_time: ISO 8601 timestamp representing the previous sync time.

        Returns:
            List of newly modified or created Document objects.
        """
        if not last_sync_time:
            return self.load_documents()

        documents: List[Document] = []
        entries = self.client.list_folder(path=self.root_path, recursive=True)

        for entry in entries:
            modified = entry.get("server_modified")
            if not modified or modified <= last_sync_time:
                continue

            path = entry.get("path_lower") or entry.get("path_display")
            if not path:
                continue
            doc = self.load_document_by_id(path)
            if doc:
                documents.append(doc)

        return documents
