"""
Notion Data Extraction & Normalization Parser.

Transforms raw Notion API JSON (page, block, database, and table responses) into our standardized
intermediate representation while retaining essential metadata, tabular schemas, and source attribution.
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
    "table": "table",
    "table_row": "table_row",
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


def extract_property_value(prop_data: Dict[str, Any]) -> Any:
    """
    Extracts a clean, typed Python value from any Notion database property object.
    Supports numbers, dates, selects, multi-selects, titles, text, checkboxes, statuses, and formulas.
    """
    if not isinstance(prop_data, dict):
        return None

    p_type = prop_data.get("type")
    if not p_type:
        return None

    if p_type == "title":
        return extract_rich_text(prop_data.get("title", []))
    elif p_type == "rich_text":
        return extract_rich_text(prop_data.get("rich_text", []))
    elif p_type == "number":
        return prop_data.get("number")
    elif p_type == "select":
        select_obj = prop_data.get("select")
        return select_obj.get("name") if select_obj else None
    elif p_type == "multi_select":
        return [s.get("name") for s in prop_data.get("multi_select", []) if s.get("name")]
    elif p_type == "date":
        date_obj = prop_data.get("date")
        if not date_obj:
            return None
        start = date_obj.get("start")
        end = date_obj.get("end")
        return f"{start} -> {end}" if end else start
    elif p_type == "checkbox":
        return prop_data.get("checkbox", False)
    elif p_type == "status":
        status_obj = prop_data.get("status")
        return status_obj.get("name") if status_obj else None
    elif p_type == "url":
        return prop_data.get("url")
    elif p_type == "email":
        return prop_data.get("email")
    elif p_type == "phone_number":
        return prop_data.get("phone_number")
    elif p_type == "formula":
        f_obj = prop_data.get("formula", {})
        f_type = f_obj.get("type")
        return f_obj.get(f_type) if f_type else None
    elif p_type == "created_time":
        return prop_data.get("created_time")
    elif p_type == "last_edited_time":
        return prop_data.get("last_edited_time")
    elif p_type == "people":
        return [p.get("name") or p.get("id") for p in prop_data.get("people", [])]
    elif p_type == "relation":
        return [r.get("id") for r in prop_data.get("relation", [])]
    
    # Fallback to general type retrieval
    return prop_data.get(p_type)


def extract_database_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts a Notion child_database (used for charts, tables, metric tracking, task boards).
    Extracts full column schemas, typed row records, and builds a summary representation.
    """
    title = block.get("child_database", {}).get("title", "")
    db_rows = block.get("database_rows", [])
    block_id = block.get("id", "")

    # Discover columns and extract row data
    columns_set = set()
    rows_data: List[Dict[str, Any]] = []

    for row in db_rows:
        row_id = row.get("id", "")
        props = row.get("properties", {})
        row_dict: Dict[str, Any] = {}

        for col_name, prop_val in props.items():
            val = extract_property_value(prop_val)
            if val is not None and val != "":
                row_dict[col_name] = val
                columns_set.add(col_name)

        if row_dict:
            rows_data.append({
                "id": row_id,
                "data": row_dict
            })

    columns_list = sorted(list(columns_set))

    # Construct descriptive summary text for search indexing
    summary_lines = [f"Database / Chart: {title or 'Untitled'} ({len(rows_data)} records)"]
    if columns_list:
        summary_lines.append(f"Columns: {', '.join(columns_list)}")

    return {
        "type": "database",
        "text": "\n".join(summary_lines),
        "block_id": block_id,
        "has_children": bool(rows_data),
        "columns": columns_list,
        "rows": rows_data,
        "total_rows": len(rows_data),
    }


def extract_table_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts a Notion simple table block and its table_row children.
    """
    table_data = block.get("table", {})
    raw_children = block.get("children", [])
    has_column_header = table_data.get("has_column_header", False)
    
    extracted_rows: List[List[str]] = []
    for child in raw_children:
        if child.get("type") == "table_row":
            cells = child.get("table_row", {}).get("cells", [])
            row_cells = [extract_rich_text(cell).strip() for cell in cells]
            extracted_rows.append(row_cells)

    headers = extracted_rows[0] if (has_column_header and extracted_rows) else []
    data_rows = extracted_rows[1:] if (has_column_header and extracted_rows) else extracted_rows

    return {
        "type": "table",
        "text": f"Table ({len(extracted_rows)} rows)",
        "block_id": block.get("id"),
        "has_children": bool(extracted_rows),
        "headers": headers,
        "rows": data_rows,
    }


def extract_block(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Converts a raw Notion block JSON into our normalized block representation.

    Filters out unsupported, media, and file blocks (PDFs, videos, audio, files, bookmarks),
    while preserving semantic knowledge blocks (headings, paragraphs, bullet lists, toggles,
    code, callouts, quotes, databases, tables) and their nested hierarchies.
    """
    block_type = block.get("type")
    if not block_type:
        return None

    # Explicitly ignore media, attachments, and web bookmarks
    if block_type in IGNORED_BLOCK_TYPES:
        return None

    # 1. Handle Databases (Charts, Data Tables, Metric Boards, Task Trackers)
    if block_type == "child_database":
        return extract_database_block(block)

    # 2. Handle Simple Inline Tables
    if block_type == "table":
        return extract_table_block(block)

    # 3. Handle child_page (nested sub-page link)
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

    # 4. Check if standard block type is supported
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
    preserving full tabular database records and hierarchies.
    """
    document = extract_page_metadata(page)

    content: List[Dict[str, Any]] = []
    for block in blocks:
        extracted = extract_block(block)
        if extracted:
            content.append(extracted)

    document["content"] = content
    return document
