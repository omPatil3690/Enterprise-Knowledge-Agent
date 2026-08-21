"""
Intermediate Document Representation for Enterprise Knowledge Agent.

This module defines the intermediate structured document schema that bridges raw platform JSON
(e.g., Notion, Confluence, Jira) and downstream stages (OKF normalization, Chunking, Embeddings, Knowledge Graph).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class BlockType(str, Enum):
    """
    Standardized block types representing structured content across enterprise platforms.
    """
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    PARAGRAPH = "paragraph"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    TO_DO = "to_do"
    TOGGLE = "toggle"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    DIVIDER = "divider"
    CHILD_PAGE = "child_page"
    CHILD_DATABASE = "child_database"
    TABLE = "table"
    TABLE_ROW = "table_row"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """
    Layer 1: Page-level metadata extracted from the source platform.

    Carries identity, source citation info, change tracking timestamps,
    and hierarchy context without keeping bulky raw API payloads.
    """
    id: str                                # Unique page/source ID (e.g., Notion page UUID)
    title: str                             # Page title
    source_platform: str = "notion"        # Platform name (notion, confluence, jira, drive)
    url: Optional[str] = None              # Direct URL to the source page for agent citations
    created_time: Optional[str] = None     # ISO 8601 creation timestamp
    last_edited_time: Optional[str] = None # ISO 8601 last modified timestamp (for incremental sync)
    parent_type: Optional[str] = None      # Type of parent ("workspace", "page_id", "database_id")
    parent_id: Optional[str] = None        # ID of parent container (for hierarchical graph links)
    created_by: Optional[str] = None       # Creator user identifier
    last_edited_by: Optional[str] = None   # Last editor user identifier
    extra: Dict[str, Any] = field(default_factory=dict) # Platform-specific extra tags/properties

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to a dictionary."""
        return asdict(self)


@dataclass
class ContentBlock:
    """
    Layer 2 & Layer 3: Block-level content with source attribution.

    Represents an atomic structural unit of knowledge (e.g. heading, paragraph, bullet point),
    retaining semantic meaning, block-specific properties, and origin metadata for citation.
    """
    id: str                                # Unique block ID
    type: BlockType                        # Normalized block type
    text: str                              # Cleaned plain text content of this block
    properties: Dict[str, Any] = field(default_factory=dict) # E.g., {"checked": True, "language": "python", "level": 1}
    raw_type: Optional[str] = None         # Original block type from the provider
    parent_id: Optional[str] = None        # Parent block/page ID for nested hierarchies (e.g., toggles)
    created_time: Optional[str] = None     # Block creation timestamp
    last_edited_time: Optional[str] = None # Block modification timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert content block to a dictionary."""
        data = asdict(self)
        data["type"] = self.type.value if isinstance(self.type, BlockType) else self.type
        return data

    def to_source_attribution(self, doc_metadata: DocumentMetadata) -> Dict[str, Any]:
        """
        Layer 3 Helper: Generates explicit source attribution for this individual block.
        Useful when an agent cites a specific sentence or chunk.
        """
        return {
            "page_id": doc_metadata.id,
            "page_title": doc_metadata.title,
            "page_url": doc_metadata.url,
            "block_id": self.id,
            "block_type": self.type.value if isinstance(self.type, BlockType) else str(self.type),
            "text": self.text,
        }


@dataclass
class Document:
    """
    Intermediate structured document container.

    Pipeline position:
        Raw Platform JSON (e.g., Notion)
               ↓
        Extraction / Cleaning
               ↓
        [ Document ]  <-- THIS STRUCTURE
               ↓
        OKF (Open Knowledge Format)
               ↓
        Chunking -> Embeddings / Graph / Search
    """
    metadata: DocumentMetadata
    blocks: List[ContentBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full document to a standard dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "blocks": [b.to_dict() for b in self.blocks]
        }

    def to_markdown(self) -> str:
        """
        Renders the document's structured blocks into clean Markdown.
        Preserves headings, lists, code fences, quotes, and callouts.
        """
        lines: List[str] = []

        for block in self.blocks:
            text = block.text.strip()
            if not text and block.type not in (BlockType.DIVIDER,):
                continue

            b_type = block.type

            if b_type == BlockType.HEADING_1:
                lines.append(f"# {text}\n")
            elif b_type == BlockType.HEADING_2:
                lines.append(f"## {text}\n")
            elif b_type == BlockType.HEADING_3:
                lines.append(f"### {text}\n")
            elif b_type == BlockType.HEADING_4:
                lines.append(f"#### {text}\n")
            elif b_type == BlockType.BULLETED_LIST_ITEM:
                lines.append(f"- {text}")
            elif b_type == BlockType.NUMBERED_LIST_ITEM:
                lines.append(f"1. {text}")
            elif b_type == BlockType.TO_DO:
                checked = block.properties.get("checked", False)
                box = "[x]" if checked else "[ ]"
                lines.append(f"- {box} {text}")
            elif b_type == BlockType.QUOTE:
                lines.append(f"> {text}\n")
            elif b_type == BlockType.CALLOUT:
                icon = block.properties.get("icon", "")
                prefix = f"💡 [{icon}] " if icon else "💡 "
                lines.append(f"> {prefix}{text}\n")
            elif b_type == BlockType.CODE:
                lang = block.properties.get("language", "")
                lines.append(f"```{lang}\n{text}\n```\n")
            elif b_type == BlockType.DIVIDER:
                lines.append("---\n")
            elif b_type == BlockType.CHILD_PAGE:
                lines.append(f"📄 Page: {text}")
            elif b_type == BlockType.CHILD_DATABASE:
                lines.append(f"🗃️ Database: {text}")
            else:
                lines.append(f"{text}\n")

        return "\n".join(lines)

    def to_plain_text(self) -> str:
        """Extracts combined plain text across all blocks."""
        return "\n".join(b.text for b in self.blocks if b.text.strip())
