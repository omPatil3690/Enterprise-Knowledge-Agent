"""
Jira Data Extraction & Normalization Parser.

Transforms raw Jira Cloud REST API JSON (projects, issues, ADF descriptions)
into our standardized intermediate representation, retaining essential metadata,
structured records, and source attribution. Converts Atlassian Document Format
(ADF) description trees into semantic block dictionaries.
"""

import re
from typing import Any, Dict, List, Optional

# ADF node types that should never be promoted to standalone blocks
IGNORED_ADF_TYPES = {
    "mediaSingle", "mediaGroup", "media", "emoji", "placeholder",
    "inlineCard", "blockCard", "hardBreak",
}


def _slug(text: str, prefix: str = "block") -> str:
    """Generates a short stable identifier from arbitrary text."""
    clean = re.sub(r"[^\w\s-]", "", text).strip().lower()
    clean = re.sub(r"[-\s]+", "_", clean)[:60]
    return clean or prefix


def build_heading(text: str, level: int = 1) -> Dict[str, Any]:
    """Builds a normalized heading block dictionary."""
    clean = text.strip()
    return {
        "type": f"heading_{min(max(level, 1), 4)}",
        "text": clean,
        "block_id": _slug(clean, "heading"),
        "level": min(max(level, 1), 4),
        "properties": {"level": min(max(level, 1), 4)},
    }


def build_paragraph(text: str) -> Dict[str, Any]:
    """Builds a normalized paragraph block dictionary."""
    clean = text.strip()
    return {
        "type": "paragraph",
        "text": clean,
        "block_id": _slug(clean, "para"),
    }


def collect_adf_text(node: Dict[str, Any]) -> str:
    """
    Recursively collects plain text from an ADF node, resolving text nodes,
    mentions, and hard breaks.
    """
    ntype = node.get("type")
    if ntype == "text":
        return node.get("text", "")
    if ntype == "mention":
        attrs = node.get("attrs") or {}
        name = attrs.get("text") or attrs.get("accessibilityLabel") or attrs.get("id") or "user"
        return f"@{name}"
    if ntype == "hardBreak":
        return "\n"

    parts: List[str] = []
    for child in node.get("content", []):
        parts.append(collect_adf_text(child))
    if ntype == "paragraph":
        parts.append("\n")
    return "".join(parts)


def adf_table_to_blocks(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Converts an ADF table node into a structured DATABASE block."""
    rows: List[List[str]] = []
    for row_node in node.get("content", []):
        if row_node.get("type") != "tableRow":
            continue
        cells: List[str] = []
        for cell in row_node.get("content", []):
            if cell.get("type") not in ("tableHeader", "tableCell"):
                continue
            cells.append(collect_adf_text(cell).strip())
        if cells:
            rows.append(cells)

    if not rows:
        return []

    header_cells = rows[0]
    body_rows = rows[1:]
    columns = header_cells or [f"Column {i + 1}" for i in range(max((len(r) for r in body_rows), default=0))]

    normalized_rows = []
    for idx, row in enumerate(body_rows, 1):
        normalized_rows.append({
            "id": str(idx),
            "data": {columns[j]: (row[j] if j < len(row) else "") for j in range(len(columns))},
        })

    return [{
        "type": "database",
        "text": "Jira Table",
        "block_id": "jira_table",
        "columns": columns,
        "rows": normalized_rows,
        "total_rows": len(normalized_rows),
    }]


def adf_node_to_blocks(node: Dict[str, Any], depth: int = 0) -> List[Dict[str, Any]]:
    """
    Recursively converts an ADF document node into normalized block dictionaries.
    """
    blocks: List[Dict[str, Any]] = []
    ntype = node.get("type")

    if ntype == "doc":
        for child in node.get("content", []):
            blocks.extend(adf_node_to_blocks(child, depth))
    elif ntype == "paragraph":
        text = collect_adf_text(node).strip()
        if text:
            blocks.append(build_paragraph(text))
    elif ntype == "heading":
        level = (node.get("attrs") or {}).get("level", 1)
        text = collect_adf_text(node).strip()
        if text:
            blocks.append(build_heading(text, level))
    elif ntype in ("bulletList", "orderedList"):
        kind = "bulleted_list_item" if ntype == "bulletList" else "numbered_list_item"
        for item in node.get("content", []):
            if item.get("type") != "listItem":
                continue
            item_text = ""
            nested: List[Dict[str, Any]] = []
            for child in item.get("content", []):
                if child.get("type") in ("bulletList", "orderedList"):
                    nested.extend(adf_node_to_blocks(child, depth + 1))
                else:
                    item_text += f"{collect_adf_text(child)} "
            entry = {
                "type": kind,
                "text": item_text.strip(),
                "block_id": _slug(item_text, "list"),
            }
            if nested:
                entry["children"] = nested
            blocks.append(entry)
    elif ntype == "codeBlock":
        language = (node.get("attrs") or {}).get("language") or ""
        text = collect_adf_text(node).strip()
        if text:
            blocks.append({
                "type": "code",
                "text": text,
                "block_id": _slug(text, "code"),
                "language": language,
                "properties": {"language": language},
            })
    elif ntype == "rule":
        blocks.append({"type": "divider", "text": "", "block_id": "divider"})
    elif ntype == "quote":
        text = collect_adf_text(node).strip()
        if text:
            blocks.append({"type": "quote", "text": text, "block_id": _slug(text, "quote")})
    elif ntype == "table":
        blocks.extend(adf_table_to_blocks(node))
    elif ntype in IGNORED_ADF_TYPES:
        pass
    else:
        for child in node.get("content", []):
            blocks.extend(adf_node_to_blocks(child, depth))

    return blocks


def description_to_blocks(description: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converts a Jira ADF description into normalized block dictionaries.
    """
    if not description:
        return []
    return adf_node_to_blocks(description)


def normalize_issue_document(issue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a single Jira issue into a normalized Document dict.
    """
    fields = issue.get("fields") or {}
    key = issue.get("key") or str(issue.get("id") or "UNKNOWN")
    summary = fields.get("summary") or "Untitled"

    issue_type = (fields.get("issuetype") or {}).get("name") or "Issue"
    status = (fields.get("status") or {}).get("name") or "Unknown"
    priority = (fields.get("priority") or {}).get("name")
    assignee = (fields.get("assignee") or {}).get("displayName")
    reporter = (fields.get("reporter") or {}).get("displayName")
    project = fields.get("project") or {}
    project_key = project.get("key") or ""
    project_name = project.get("name") or project_key
    labels = fields.get("labels") or []
    components = [
        c.get("name") for c in (fields.get("components") or []) if c.get("name")
    ]
    parent = fields.get("parent") or {}
    parent_key = parent.get("key")

    self_link = issue.get("self") or ""
    browse_url = None
    if self_link:
        browse_url = re.sub(r"/rest/api/\d+/issue/", "/browse/", self_link)

    doc: Dict[str, Any] = {
        "source": "jira",
        "source_id": key,
        "title": f"{key}: {summary}",
        "url": browse_url,
        "parent_type": "project",
        "parent_id": project_key,
        "created_at": fields.get("created"),
        "updated_at": fields.get("updated"),
        "created_by": reporter,
        "last_edited_by": None,
        "extra": {
            "project_key": project_key,
            "project_name": project_name,
            "issue_type": issue_type,
            "status": status,
            "priority": priority,
            "assignee": assignee,
            "reporter": reporter,
            "labels": labels,
            "components": components,
            "parent_key": parent_key,
            "subtask": bool((fields.get("issuetype") or {}).get("subtask")),
            "resolution": (fields.get("resolution") or {}).get("name"),
        },
    }

    blocks: List[Dict[str, Any]] = []
    blocks.append(build_heading(f"{key}: {summary}", level=1))

    meta_lines = [f"Type: {issue_type}", f"Status: {status}"]
    if priority:
        meta_lines.append(f"Priority: {priority}")
    if assignee:
        meta_lines.append(f"Assignee: {assignee}")
    if reporter:
        meta_lines.append(f"Reporter: {reporter}")
    if project_name:
        meta_lines.append(f"Project: {project_name}")
    if labels:
        meta_lines.append(f"Labels: {', '.join(labels)}")
    if components:
        meta_lines.append(f"Components: {', '.join(components)}")
    if browse_url:
        meta_lines.append(f"URL: {browse_url}")
    blocks.append({
        "type": "callout",
        "text": "\n".join(meta_lines),
        "block_id": "jira_meta",
        "properties": {"icon": "🎯"},
    })

    description = fields.get("description")
    if description:
        blocks.append(build_heading("Description", level=2))
        blocks.extend(description_to_blocks(description))

    blocks.append({
        "type": "database",
        "text": f"Issue: {key}",
        "block_id": f"issue_{key}",
        "columns": ["Key", "Summary", "Type", "Status", "Priority", "Assignee", "Labels"],
        "rows": [{
            "id": key,
            "data": {
                "Key": key,
                "Summary": summary,
                "Type": issue_type,
                "Status": status,
                "Priority": priority or "",
                "Assignee": assignee or "",
                "Labels": ", ".join(labels),
            },
        }],
        "total_rows": 1,
    })

    doc["content"] = blocks
    return doc


def normalize_project_document(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a Jira project into a normalized Document dict.
    """
    lead = project.get("lead") or {}
    url = project.get("self") or ""
    if url:
        url = re.sub(r"/rest/api/\d+/project/", "/browse/", url)

    doc: Dict[str, Any] = {
        "source": "jira",
        "source_id": project.get("key") or str(project.get("id") or ""),
        "title": project.get("name") or project.get("key") or "Untitled Project",
        "url": url,
        "parent_type": "jira_site",
        "parent_id": "jira",
        "created_at": None,
        "updated_at": None,
        "created_by": None,
        "last_edited_by": lead.get("displayName") or lead.get("name"),
        "extra": {
            "project_key": project.get("key"),
            "project_type": project.get("projectTypeKey"),
            "style": project.get("style"),
            "lead": lead.get("displayName") or lead.get("name"),
        },
    }

    blocks: List[Dict[str, Any]] = []
    blocks.append(build_heading(project.get("name") or project.get("key") or "Project", level=1))
    if project.get("key"):
        blocks.append(build_paragraph(f"Project Key: {project.get('key')}"))
    if project.get("projectTypeKey"):
        blocks.append(build_paragraph(f"Project Type: {project.get('projectTypeKey')}"))
    if lead.get("displayName"):
        blocks.append(build_paragraph(f"Project Lead: {lead.get('displayName')}"))
    if url:
        blocks.append(build_paragraph(f"URL: {url}"))

    blocks.append({
        "type": "database",
        "text": f"Project: {project.get('name')}",
        "block_id": f"project_{project.get('key')}",
        "columns": ["Key", "Name", "Type", "Style", "Lead"],
        "rows": [{
            "id": project.get("key") or "",
            "data": {
                "Key": project.get("key") or "",
                "Name": project.get("name") or "",
                "Type": project.get("projectTypeKey") or "",
                "Style": project.get("style") or "",
                "Lead": lead.get("displayName") or "",
            },
        }],
        "total_rows": 1,
    })

    doc["content"] = blocks
    return doc