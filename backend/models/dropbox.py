"""
Canonical Dropbox Models for Enterprise Knowledge Agent.

Defines provider-independent Dropbox representations (DropboxFile, DropboxFolder,
DropboxEntry) that bridge raw Dropbox API payloads to the intermediate Document
and OKF knowledge representation pipelines.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata


@dataclass
class DropboxEntry:
    """
    A single entry (file or folder) surfaced from a Dropbox folder listing.
    Used both as a standalone item and as a child row within a folder index table.
    """
    name: str
    path_lower: str
    kind: str = "file"                       # "file" | "folder"
    size: Optional[int] = None
    server_modified: Optional[str] = None
    client_modified: Optional[str] = None
    entry_id: Optional[str] = None
    rev: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def as_table_row(self) -> Dict[str, Any]:
        """Converts the entry into a row dict compatible with a DATABASE ContentBlock."""
        return {
            "id": self.entry_id or self.path_lower,
            "data": {
                "Name": self.name,
                "Path": self.path_lower,
                "Size": self.size,
                "Modified": self.server_modified,
            },
        }


@dataclass
class DropboxFile:
    """
    Provider-canonical Dropbox file model.
    """
    path_lower: str
    name: str
    parent_path: str = ""
    size: int = 0
    server_modified: Optional[str] = None
    client_modified: Optional[str] = None
    entry_id: Optional[str] = None
    rev: Optional[str] = None
    content: Optional[str] = None             # Downloaded text content (if text file)

    @classmethod
    def from_api(cls, entry: Dict[str, Any], content: Optional[str] = None) -> "DropboxFile":
        path_lower = entry.get("path_lower") or entry.get("path_display") or entry.get("name", "file")
        name = entry.get("name") or path_lower.rsplit("/", 1)[-1]
        parent_path = path_lower.rsplit("/", 1)[0] if "/" in path_lower else ""
        return cls(
            path_lower=path_lower,
            name=name,
            parent_path=parent_path,
            size=entry.get("size") or 0,
            server_modified=entry.get("server_modified"),
            client_modified=entry.get("client_modified"),
            entry_id=entry.get("id"),
            rev=entry.get("rev"),
            content=content,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_intermediate_document(self) -> Document:
        """Converts this canonical file into the system's universal intermediate Document."""
        metadata = DocumentMetadata(
            id=self.entry_id or self.path_lower,
            title=self.path_lower.strip("/"),
            source_platform="dropbox",
            url=f"dropbox://{self.path_lower}",
            created_time=self.client_modified,
            last_edited_time=self.server_modified,
            parent_type="folder",
            parent_id=self.parent_path,
            extra={
                "kind": "file",
                "size": self.size,
                "name": self.name,
                "path_lower": self.path_lower,
                "rev": self.rev,
            },
        )

        blocks: List[ContentBlock] = []

        blocks.append(
            ContentBlock(
                id=f"{self.path_lower}_heading",
                type=BlockType.HEADING,
                text=f"File: {self.name}",
                properties={"level": 1},
            )
        )
        blocks.append(
            ContentBlock(
                id=f"{self.path_lower}_path",
                type=BlockType.PARAGRAPH,
                text=f"Path: {self.path_lower}",
            )
        )
        if self.size:
            blocks.append(
                ContentBlock(
                    id=f"{self.path_lower}_size",
                    type=BlockType.PARAGRAPH,
                    text=f"Size: {self.size} bytes",
                )
            )
        if self.content and self.content.strip():
            blocks.append(
                ContentBlock(
                    id=f"{self.path_lower}_content_heading",
                    type=BlockType.HEADING_2,
                    text="Content",
                )
            )
            blocks.append(
                ContentBlock(
                    id=f"{self.path_lower}_content",
                    type=BlockType.PARAGRAPH,
                    text=self.content.strip(),
                )
            )

        return Document(metadata=metadata, blocks=blocks)


@dataclass
class DropboxFolder:
    """
    Provider-canonical Dropbox folder model.

    Carries the folder's own metadata plus its immediate child entries, rendered
    as a structured database table for graph/table extraction.
    """
    path_lower: str
    name: str
    parent_path: str = ""
    entry_id: Optional[str] = None
    server_modified: Optional[str] = None
    children: List[DropboxEntry] = field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        entry: Dict[str, Any],
        children: Optional[List[Dict[str, Any]]] = None,
    ) -> "DropboxFolder":
        path_lower = entry.get("path_lower") or entry.get("path_display") or entry.get("name", "folder")
        name = entry.get("name") or path_lower.rsplit("/", 1)[-1]
        parent_path = path_lower.rsplit("/", 1)[0] if "/" in path_lower else ""

        parsed_children: List[DropboxEntry] = []
        for c in children or []:
            c_path = c.get("path_lower") or c.get("path_display") or ""
            parsed_children.append(
                DropboxEntry(
                    name=c.get("name", ""),
                    path_lower=c_path,
                    kind=c.get(".tag", "file"),
                    size=c.get("size"),
                    server_modified=c.get("server_modified"),
                    client_modified=c.get("client_modified"),
                    entry_id=c.get("id"),
                    rev=c.get("rev"),
                )
            )

        return cls(
            path_lower=path_lower,
            name=name,
            parent_path=parent_path,
            entry_id=entry.get("id"),
            server_modified=entry.get("server_modified"),
            children=parsed_children,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["children"] = [c.to_dict() for c in self.children]
        return d

    def to_intermediate_document(self) -> Document:
        """Converts this canonical folder into the system's universal intermediate Document."""
        metadata = DocumentMetadata(
            id=self.entry_id or self.path_lower,
            title=self.path_lower.strip("/"),
            source_platform="dropbox",
            url=f"dropbox://{self.path_lower}",
            created_time=self.server_modified,
            last_edited_time=self.server_modified,
            parent_type="folder",
            parent_id=self.parent_path,
            extra={
                "kind": "folder",
                "name": self.name,
                "path_lower": self.path_lower,
            },
        )

        blocks: List[ContentBlock] = []

        blocks.append(
            ContentBlock(
                id=f"{self.path_lower}_heading",
                type=BlockType.HEADING,
                text=f"Folder: {self.name}",
                properties={"level": 1},
            )
        )
        blocks.append(
            ContentBlock(
                id=f"{self.path_lower}_path",
                type=BlockType.PARAGRAPH,
                text=f"Path: {self.path_lower}",
            )
        )

        files = [c for c in self.children if c.kind == "file"]
        subs = [c for c in self.children if c.kind == "folder"]
        blocks.append(
            ContentBlock(
                id=f"{self.path_lower}_summary",
                type=BlockType.PARAGRAPH,
                text=f"Contains {len(files)} file(s) and {len(subs)} subfolder(s).",
            )
        )

        if files:
            blocks.append(
                ContentBlock(
                    id=f"folder_{self.path_lower}",
                    type=BlockType.DATABASE,
                    text=f"Folder Contents: {self.path_lower}",
                    columns=["Name", "Path", "Size", "Modified"],
                    rows=[c.as_table_row() for c in files],
                    properties={"total_rows": len(files)},
                )
            )

        return Document(metadata=metadata, blocks=blocks)
