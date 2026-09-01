"""
Dropbox Data Extraction & Normalization Parser.

Transforms raw Dropbox API JSON (files, folders, metadata) into our standardized
intermediate representation, retaining essential metadata and structured records,
and filtering non-textual assets (images, video, audio, archives) from the pipeline.
"""

from typing import Any, Dict, List, Optional

# File extensions explicitly ignored for text/knowledge retrieval
IGNORED_TEXT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".ico", ".bmp", ".tiff", ".pdf", ".zip", ".tar", ".gz",
    ".7z", ".rar", ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".woff", ".woff2", ".ttf", ".eot", ".exe", ".dll", ".so",
    ".dylib", ".psd", ".ai", ".eps",
}

# Known binary / generated files to skip
IGNORED_FILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Gemfile.lock", "Cargo.lock", "Pipfile.lock",
}

# Markdown / text-friendly extensions worth ingesting as content
PREFERRED_TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst", ".text",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp",
    ".h", ".go", ".rs", ".rb", ".php", ".html", ".htm", ".css",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".tsv", ".sql", ".sh", ".bash", ".bat", ".ps1",
}


def is_text_file(path_lower: str) -> bool:
    """Returns False for known binary extensions and generated lock files."""
    name = path_lower.rsplit("/", 1)[-1]
    if name in IGNORED_FILE_NAMES:
        return False
    ext_start = path_lower.rfind(".")
    if ext_start == -1:
        return True
    ext = path_lower[ext_start:].lower()
    return ext not in IGNORED_TEXT_EXTENSIONS


def build_heading(text: str, level: int = 1) -> Dict[str, Any]:
    """Builds a normalized heading block dictionary."""
    return {
        "type": "heading",
        "text": text.strip(),
        "block_id": text.strip().lower().replace(" ", "_")[:60],
        "level": level,
    }


def build_paragraph(text: str) -> Dict[str, Any]:
    """Builds a normalized paragraph block dictionary."""
    return {
        "type": "paragraph",
        "text": text.strip(),
        "block_id": text.strip().lower().replace(" ", "_")[:60],
    }


def extract_file_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a Dropbox file metadata entry into a Document dict.
    """
    path_lower = entry.get("path_lower") or entry.get("path_display") or entry.get("name", "file")
    name = entry.get("name") or path_lower.rsplit("/", 1)[-1]
    parent_path = path_lower.rsplit("/", 1)[0] if "/" in path_lower else ""

    return {
        "source": "dropbox",
        "source_id": entry.get("id") or path_lower,
        "title": path_lower.strip("/"),
        "url": None,
        "parent_type": "folder",
        "parent_id": parent_path,
        "created_at": entry.get("client_modified"),
        "updated_at": entry.get("server_modified"),
        "created_by": None,
        "last_edited_by": None,
        "extra": {
            "kind": entry.get(".tag", "file"),
            "size": entry.get("size"),
            "rev": entry.get("rev"),
            "name": name,
            "path_lower": path_lower,
        },
    }


def normalize_file_document(
    entry: Dict[str, Any],
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Combines a file's metadata and optional text content into a normalized Document dict.
    """
    doc = extract_file_entry(entry)
    blocks: List[Dict[str, Any]] = []

    path_lower = doc["title"]
    name = doc["extra"].get("name") or path_lower

    blocks.append(build_heading(f"File: {name}", level=1))
    blocks.append(build_paragraph(f"Path: {path_lower}"))
    if doc["extra"].get("size") is not None:
        blocks.append(build_paragraph(f"Size: {doc['extra']['size']} bytes"))

    if content and content.strip():
        blocks.append(build_heading("Content", level=2))
        blocks.append(build_paragraph(content.strip()))

    doc["content"] = blocks
    return doc


def normalize_folder_document(
    entry: Dict[str, Any],
    children: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Combines a folder's metadata and its child entries into a normalized Document dict.
    Children are represented as a structured database block for graph/table extraction.
    """
    doc = extract_file_entry(entry)
    blocks: List[Dict[str, Any]] = []

    path_lower = doc["title"]
    doc["extra"]["kind"] = "folder"
    doc["extra"]["name"] = (entry.get("name") or path_lower.rsplit("/", 1)[-1])

    blocks.append(build_heading(f"Folder: {doc['extra']['name']}", level=1))
    blocks.append(build_paragraph(f"Path: {path_lower}"))

    if children:
        files = [c for c in children if c.get(".tag") == "file"]
        subs = [c for c in children if c.get(".tag") == "folder"]
        blocks.append(build_paragraph(f"Contains {len(files)} file(s) and {len(subs)} subfolder(s)."))

        # Structured table of child files
        rows = []
        for c in children:
            if c.get(".tag") == "file":
                rows.append({
                    "id": c.get("id") or c.get("path_lower", ""),
                    "data": {
                        "Name": c.get("name", ""),
                        "Path": c.get("path_lower", ""),
                        "Size": c.get("size"),
                        "Modified": c.get("server_modified"),
                    },
                })
        if rows:
            blocks.append({
                "type": "database",
                "text": f"Folder Contents: {path_lower}",
                "block_id": f"folder_{path_lower}",
                "columns": ["Name", "Path", "Size", "Modified"],
                "rows": rows,
                "total_rows": len(rows),
            })

    doc["content"] = blocks
    return doc
