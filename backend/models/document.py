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
    HEADING = "heading"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    PARAGRAPH = "paragraph"
    BULLET = "bullet"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBER = "number"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    TO_DO = "to_do"
    TOGGLE = "toggle"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    DIVIDER = "divider"
    DATABASE = "database"
    CHILD_PAGE = "child_page"
    CHILD_PAGE_LINK = "child_page_link"
    CHILD_DATABASE = "child_database"
    TABLE = "table"
    TABLE_ROW = "table_row"
    IMAGE = "image"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> BlockType:
        """Safely parses a string into a BlockType enum with fallback to UNKNOWN."""
        clean = value.lower().strip()
        try:
            return cls(clean)
        except ValueError:
            return cls.UNKNOWN


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

    Represents an atomic structural unit of knowledge (e.g. heading, paragraph, bullet point, database table),
    retaining semantic meaning, structured records (columns & rows for databases/charts), and origin metadata.
    """
    id: str                                # Unique block ID
    type: BlockType                        # Normalized block type
    text: str                              # Cleaned plain text content of this block
    properties: Dict[str, Any] = field(default_factory=dict) # E.g., {"checked": True, "language": "python", "level": 1}
    raw_type: Optional[str] = None         # Original block type from the provider
    parent_id: Optional[str] = None        # Parent block/page ID for nested hierarchies (e.g., toggles)
    children: List[ContentBlock] = field(default_factory=list) # Nested child blocks
    columns: List[str] = field(default_factory=list)           # Column headers for databases/tables
    rows: List[Dict[str, Any]] = field(default_factory=list)   # Structured records for databases/tables
    created_time: Optional[str] = None     # Block creation timestamp
    last_edited_time: Optional[str] = None # Block modification timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert content block to a dictionary."""
        d: Dict[str, Any] = {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, BlockType) else str(self.type),
            "text": self.text,
            "properties": self.properties,
        }
        if self.columns:
            d["columns"] = self.columns
        if self.rows:
            d["rows"] = self.rows
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.raw_type:
            d["raw_type"] = self.raw_type
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.created_time:
            d["created_time"] = self.created_time
        if self.last_edited_time:
            d["last_edited_time"] = self.last_edited_time
        return d

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
        Preserves headings, lists, code fences, quotes, callouts, and tabular databases/charts.
        """
        lines: List[str] = []

        def render_block(block: ContentBlock, depth: int = 0) -> None:
            text = block.text.strip()
            indent = "  " * depth
            b_type = block.type

            if b_type in (BlockType.HEADING, BlockType.HEADING_1):
                level = block.properties.get("level", 1)
                prefix = "#" * max(1, min(6, level))
                lines.append(f"\n{prefix} {text}\n")
            elif b_type == BlockType.HEADING_2:
                lines.append(f"\n## {text}\n")
            elif b_type == BlockType.HEADING_3:
                lines.append(f"\n### {text}\n")
            elif b_type == BlockType.HEADING_4:
                lines.append(f"\n#### {text}\n")
            elif b_type in (BlockType.BULLET, BlockType.BULLETED_LIST_ITEM):
                lines.append(f"{indent}- {text}")
            elif b_type in (BlockType.NUMBER, BlockType.NUMBERED_LIST_ITEM):
                lines.append(f"{indent}1. {text}")
            elif b_type == BlockType.TO_DO:
                checked = block.properties.get("checked", False)
                box = "[x]" if checked else "[ ]"
                lines.append(f"{indent}- {box} {text}")
            elif b_type == BlockType.TOGGLE:
                lines.append(f"\n{indent}<details><summary>{text}</summary>\n")
            elif b_type == BlockType.QUOTE:
                lines.append(f"{indent}> {text}\n")
            elif b_type == BlockType.CALLOUT:
                icon = block.properties.get("icon", "")
                prefix = f"💡 [{icon}] " if icon else "💡 "
                lines.append(f"\n{indent}> {prefix}{text}\n")
            elif b_type == BlockType.CODE:
                lang = block.properties.get("language", "")
                lines.append(f"\n```{lang}\n{text}\n```\n")
            elif b_type == BlockType.DIVIDER:
                lines.append("\n---\n")
            elif b_type in (BlockType.CHILD_PAGE, BlockType.CHILD_PAGE_LINK):
                lines.append(f"{indent}📄 Page: {text}")
            elif b_type in (BlockType.DATABASE, BlockType.CHILD_DATABASE):
                # Render database / chart as Markdown Table
                lines.append(f"\n### 📊 {text.splitlines()[0] if text else 'Database'}\n")
                if block.columns and block.rows:
                    cols = block.columns
                    header_line = "| " + " | ".join(cols) + " |"
                    sep_line = "| " + " | ".join(["---"] * len(cols)) + " |"
                    lines.append(header_line)
                    lines.append(sep_line)
                    for r in block.rows:
                        row_data = r.get("data", r) if isinstance(r, dict) else {}
                        row_cells = [str(row_data.get(c, "")).replace("|", "\\|").replace("\n", " ") for c in cols]
                        lines.append("| " + " | ".join(row_cells) + " |")
                    lines.append("")
            elif b_type in (BlockType.TABLE,):
                lines.append(f"\n### 📋 {text}\n")
                if block.columns and block.rows:
                    cols = block.columns
                    header_line = "| " + " | ".join(cols) + " |"
                    sep_line = "| " + " | ".join(["---"] * len(cols)) + " |"
                    lines.append(header_line)
                    lines.append(sep_line)
                    for r in block.rows:
                        row_cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in r] if isinstance(r, list) else []
                        lines.append("| " + " | ".join(row_cells) + " |")
                    lines.append("")
            else:
                if text:
                    lines.append(f"{indent}{text}\n")

            # Recursively render children with indentation
            for child in block.children:
                render_block(child, depth=depth + 1)

            if b_type == BlockType.TOGGLE:
                lines.append(f"{indent}</details>\n")

        for block in self.blocks:
            render_block(block)

        return "\n".join(lines)

    def to_plain_text(self) -> str:
        """Extracts combined plain text across all blocks recursively."""
        texts: List[str] = []

        def collect_text(block: ContentBlock) -> None:
            if block.text.strip():
                texts.append(block.text.strip())
            for r in block.rows:
                if isinstance(r, dict) and "data" in r:
                    texts.append(", ".join(f"{k}: {v}" for k, v in r["data"].items()))
            for child in block.children:
                collect_text(child)

        for block in self.blocks:
            collect_text(block)

        return "\n".join(texts)
