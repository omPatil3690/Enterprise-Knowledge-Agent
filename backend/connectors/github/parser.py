"""
GitHub Data Extraction & Normalization Parser.

Transforms raw GitHub API JSON (repositories, issues, pull requests, file contents)
into our standardized intermediate representation, retaining essential metadata,
structured records, and source attribution. Filters out binary files and non-textual
assets (images, videos, audio, archives) from the knowledge pipeline.
"""

from typing import Any, Dict, List, Optional

# File extensions and names explicitly ignored for text/knowledge retrieval
IGNORED_TEXT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".ico", ".bmp", ".tiff", ".pdf", ".zip", ".tar", ".gz",
    ".7z", ".rar", ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".woff", ".woff2", ".ttf", ".eot", ".exe", ".dll", ".so", ".dylib",
}

# Files commonly useful as high-signal repository documentation
PRIORITY_FILES = {
    "README.md", "readme.md", "README.rst", "README.txt",
    "LICENSE", "LICENSE.md", "CONTRIBUTING.md", "CHANGELOG.md",
}

# Large generated/packaging files that add noise rather than knowledge
IGNORED_FILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Gemfile.lock", "Cargo.lock", "Pipfile.lock",
}


def is_text_file(path: str) -> bool:
    """Returns False for known binary/extensions and generated lock files."""
    name = path.rsplit("/", 1)[-1]
    if name in IGNORED_FILE_NAMES:
        return False
    ext_start = path.rfind(".")
    if ext_start == -1:
        return True
    ext = path[ext_start:].lower()
    return ext not in IGNORED_TEXT_EXTENSIONS


def build_code_block(filename: str, content: str) -> Dict[str, Any]:
    """Normalizes a file's content into a CODE block with language metadata."""
    lang = filename.split(".")[-1] if "." in filename else "plain text"
    return {
        "type": "code",
        "text": content.strip(),
        "block_id": filename,
        "language": lang,
    }


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


def extract_issue_blocks(issue: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalizes a single issue or pull request into content blocks.
    Preserves title, body, state, labels, and essential metadata as paragraphs.
    """
    blocks: List[Dict[str, Any]] = []

    number = issue.get("number")
    title = issue.get("title") or "Untitled"
    is_pr = "pull_request" in issue

    kind = "Pull Request" if is_pr else "Issue"
    blocks.append(build_heading(f"{kind} #{number}: {title}", level=2))

    state = issue.get("state", "open")
    blocks.append(build_paragraph(f"State: {state}"))

    labels = [label.get("name") for label in issue.get("labels", []) if label.get("name")]
    if labels:
        blocks.append(build_paragraph(f"Labels: {', '.join(labels)}"))

    body = (issue.get("body") or "").strip()
    if body:
        blocks.append(build_paragraph(body))

    user = (issue.get("user") or {}).get("login")
    if user:
        blocks.append(build_paragraph(f"Opened by: {user}"))

    return blocks


def normalize_repo_metadata(repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts high-signal repository-level metadata into our document format.
    """
    owner = (repo.get("owner") or {}).get("login") or "unknown"
    name = repo.get("name") or "untitled"

    return {
        "source": "github",
        "source_id": str(repo.get("id") or name),
        "title": repo.get("full_name") or f"{owner}/{name}",
        "url": repo.get("html_url"),
        "parent_type": "organization" if repo.get("owner", {}).get("type") == "Organization" else "user",
        "parent_id": owner,
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "created_by": owner,
        "last_edited_by": owner,
        "extra": {
            "private": repo.get("private", False),
            "description": repo.get("description"),
            "default_branch": repo.get("default_branch"),
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "owner": owner,
            "clone_url": repo.get("clone_url"),
            "topics": repo.get("topics", []),
        },
    }


def build_repo_overview_blocks(repo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds a README-style overview of the repository as content blocks.
    """
    blocks: List[Dict[str, Any]] = []
    blocks.append(build_heading("Repository Overview", level=1))

    description = repo.get("description")
    if description:
        blocks.append(build_paragraph(description))

    blocks.append(build_heading("Metadata", level=2))
    meta_lines = [
        f"Owner: {(repo.get('owner') or {}).get('login', 'unknown')}",
        f"Default Branch: {repo.get('default_branch', 'main')}",
        f"Primary Language: {repo.get('language') or 'unknown'}",
        f"Stars: {repo.get('stargazers_count', 0)}",
        f"Forks: {repo.get('forks_count', 0)}",
        f"Open Issues: {repo.get('open_issues_count', 0)}",
        f"URL: {repo.get('html_url')}",
    ]
    topics = repo.get("topics", [])
    if topics:
        meta_lines.append(f"Topics: {', '.join(topics)}")
    for line in meta_lines:
        blocks.append(build_paragraph(line))

    return blocks


def normalize_repo_document(
    repo: Dict[str, Any],
    readme_content: Optional[str] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Combines repository metadata, optional README, and issues into a normalized Document dict.
    """
    doc = normalize_repo_metadata(repo)
    content: List[Dict[str, Any]] = []

    content.extend(build_repo_overview_blocks(repo))

    if readme_content and readme_content.strip():
        content.append(build_heading("README", level=1))
        content.append({"type": "paragraph", "text": readme_content.strip(), "block_id": "readme"})

    if issues:
        content.append(build_heading(f"Issues & Pull Requests ({len(issues)})", level=1))
        for issue in issues:
            content.extend(extract_issue_blocks(issue))

    # Include structured tabular data (repo metadata) for OKF structured_data extraction
    content.append({
        "type": "database",
        "text": f"Repository: {doc['title']} ({doc['extra'].get('default_branch')})",
        "block_id": "repo_metrics",
        "columns": ["Owner", "Stars", "Forks", "Open Issues", "Language"],
        "rows": [{
            "id": str(repo.get("id", "")),
            "data": {
                "Owner": doc["extra"].get("owner"),
                "Stars": doc["extra"].get("stars"),
                "Forks": doc["extra"].get("forks"),
                "Open Issues": doc["extra"].get("open_issues"),
                "Language": doc["extra"].get("language") or "unknown",
            },
        }],
        "total_rows": 1,
    })

    doc["content"] = content
    return doc


def normalize_issue_document(issue: Dict[str, Any], repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a single issue or pull request into a standalone normalized Document dict.
    """
    owner = (repo.get("owner") or {}).get("login") or "unknown"
    repo_name = repo.get("name") or "unknown"
    is_pr = "pull_request" in issue
    author = (issue.get("user") or {}).get("login") or "unknown"
    last_editor = (issue.get("closed_by") or {}).get("login") or (issue.get("updated_by") or {}).get("login") or author

    doc = {
        "source": "github",
        "source_id": str(issue.get("number") or ""),
        "title": f"{repo_name}#{issue.get('number', '')}: {issue.get('title') or 'Untitled'}",
        "url": issue.get("html_url"),
        "parent_type": "repository",
        "parent_id": f"{owner}/{repo_name}",
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "created_by": author,
        "last_edited_by": last_editor,
        "extra": {
            "is_pr": is_pr,
            "state": issue.get("state"),
            "author": author,
            "labels": [label.get("name") for label in issue.get("labels", []) if label.get("name")],
            "comments": issue.get("comments", 0),
            "pull_request": bool(is_pr),
        },
    }

    doc["content"] = extract_issue_blocks(issue)
    return doc
