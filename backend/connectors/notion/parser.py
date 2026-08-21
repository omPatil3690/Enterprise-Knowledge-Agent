"""
Notion Data Extraction & Normalization Parser.

Transforms raw Notion API JSON (page, block, and database responses) into our standardized
intermediate representation while retaining essential metadata, hierarchy, and source attribution.
Filters out unsupported or non-textual blocks (PDFs, videos, audios, files, and bookmarks).
"""

from typing import Any, Dict, List, Optional

# Blocks explicitly ignored for text/knowledge retrieval
IGNORED_BLOCK_TYPES = {
    "pdf",           # PDF file embeds
    "video",         # Video embeds/files
    "audio",         # Audio embeds/files
    "file",          # Uploaded file attachments
    "bookmark",      # Web bookmarks / preview links
    "embed",         # Third-party embeds (Figma, Loom, etc.)
    "image",         # Image files
    "link_preview",  # URL card previews
    "divider",       # Visual separator lines (no semantic knowledge)
    "unsupported",   # Blocks not supported by Notion API
}

# Supported semantic block types mapped to normalized names
SUPPORTED_BLOCK_TYPES = {
    "paragraph": "paragraph",
    "heading_1": "heading",
    "heading_2": "heading",
    "heading_3": "heading",
    "heading_4": "heading",
    "bulleted_list_item": "bullet",
    "numbered_list_item": "number",
    "to_do": "to_do",
    "toggle": "toggle",
    "code": "code",
    "quote": "quote",
    "callout": "callout",
}


def extract_rich_text(rich_text: List[Dict[str, Any]]) -> str:
    """
    Extracts and concatenates plain text from Notion's rich_text array.

    Notion rich_text items can be text, mentions, equations, or styled words.
    For semantic knowledge representation, we extract the human-readable plain_text.
    """
    if not rich_text:
        return ""

    texts = []
    for item in rich_text:
        plain = item.get("plain_text")
        if plain:
            texts.append(plain)

    return "".join(texts)


def extract_block(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Converts a raw Notion block JSON into our normalized block representation.

    Filters out unsupported, media, and file blocks (PDFs, videos, audio, files, bookmarks),
    while preserving semantic knowledge blocks (headings, paragraphs, bullet lists, toggles,
    code, callouts, quotes, databases) and their nested hierarchies.
    """
    block_type = block.get("type")
    if not block_type:
        return None

    # Explicitly ignore media, attachments, and web bookmarks
    if block_type in IGNORED_BLOCK_TYPES:
        return None

    # Handle child_database (e.g. "Todo List" inline database)
    if block_type == "child_database":
        title = block.get("child_database", {}).get("title", "")
        db_rows = block.get("database_rows", [])
        
        extracted_db: Dict[str, Any] = {
            "type": "database",
            "text": title.strip() or "Database",
            "block_id": block.get("id"),
            "has_children": bool(db_rows),
        }

        if db_rows:
            row_items = []
            for row in db_rows:
                row_title = ""
                is_checked = False
                props = row.get("properties", {})
                
                for p_val in props.values():
                    if isinstance(p_val, dict):
                        if p_val.get("type") == "title":
                            row_title = extract_rich_text(p_val.get("title", []))
                        elif p_val.get("type") == "checkbox":
                            is_checked = p_val.get("checkbox", False)
                        elif p_val.get("type") == "status":
                            status_name = p_val.get("status", {}).get("name", "")
                            if status_name.lower() in ("done", "completed"):
                                is_checked = True
                
                if row_title.strip():
                    row_items.append({
                        "type": "to_do",
                        "text": row_title.strip(),
                        "block_id": row.get("id"),
                        "checked": is_checked,
                    })
            
            if row_items:
                extracted_db["children"] = row_items

        return extracted_db

    # Handle child_page (nested sub-page link)
    if block_type == "child_page":
        title = block.get("child_page", {}).get("title", "")
        raw_children = block.get("children", [])
        extracted_page_link: Dict[str, Any] = {
            "type": "child_page_link",
            "text": title.strip(),
            "block_id": block.get("id"),
            "has_children": block.get("has_children", False),
        }
        if raw_children:
            normalized_children = []
            for child in raw_children:
                child_extracted = extract_block(child)
                if child_extracted:
                    normalized_children.append(child_extracted)
            if normalized_children:
                extracted_page_link["children"] = normalized_children
        return extracted_page_link

    # Check if block type is supported
    if block_type not in SUPPORTED_BLOCK_TYPES:
        return None

    block_data = block.get(block_type, {})
    if not block_data:
        return None

    rich_text = block_data.get("rich_text", [])
    text = extract_rich_text(rich_text).strip()

    raw_children = block.get("children", [])
    
    # Skip empty blocks if they have no nested children
    if not text and not raw_children:
        return None

    extracted: Dict[str, Any] = {
        "type": SUPPORTED_BLOCK_TYPES[block_type],
        "text": text,
        "block_id": block.get("id"),
        "has_children": block.get("has_children", False),
    }

    # Extract block-specific metadata
    if block_type == "code":
        extracted["language"] = block_data.get("language", "plain text")
    elif block_type == "to_do":
        extracted["checked"] = block_data.get("checked", False)
    elif block_type.startswith("heading"):
        level_str = block_type.split("_")[-1]
        extracted["level"] = int(level_str) if level_str.isdigit() else 1

    # Recursively normalize nested children (e.g. inside toggles or sub-lists)
    if raw_children:
        normalized_children = []
        for child in raw_children:
            child_extracted = extract_block(child)
            if child_extracted:
                normalized_children.append(child_extracted)
        if normalized_children:
            extracted["children"] = normalized_children

    return extracted


def extract_page_metadata(page: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts high-signal page-level metadata from a Notion page or block response.

    Handles:
    - /v1/pages/{id} format: where title is inside properties (e.g. properties.title or properties.Name)
    - /v1/blocks/{id} format: where title is inside child_page.title
    """
    title = ""

    # Case 1: Standard Page Object (/v1/pages/{id})
    properties = page.get("properties", {})
    if properties:
        for prop in properties.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_parts = prop.get("title", [])
                title = extract_rich_text(title_parts)
                if title:
                    break

    # Case 2: Block Object for a page (/v1/blocks/{id} with type="child_page")
    if not title and page.get("type") == "child_page":
        title = page.get("child_page", {}).get("title", "")

    # Fallback to Untitled if no title was set
    if not title.strip():
        title = "Untitled"

    # Determine parent information
    parent_obj = page.get("parent", {})
    parent_type = parent_obj.get("type")
    parent_id = parent_obj.get(parent_type) if parent_type else None

    return {
        "source": "notion",
        "source_id": page.get("id"),
        "title": title.strip(),
        "url": page.get("url"),
        "parent_type": parent_type,
        "parent_id": parent_id,
        "created_at": page.get("created_time"),
        "updated_at": page.get("last_edited_time"),
    }


def normalize_page(page: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combines page metadata and block extraction into a clean normalized Document dictionary,
    filtering out media/files/bookmarks and preserving block hierarchies.
    """
    document = extract_page_metadata(page)

    content: List[Dict[str, Any]] = []
    for block in blocks:
        extracted = extract_block(block)
        if extracted:
            content.append(extracted)

    document["content"] = content
    return document
