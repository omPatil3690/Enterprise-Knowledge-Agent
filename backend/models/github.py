"""
Canonical GitHub Models for Enterprise Knowledge Agent.

Defines provider-independent GitHub representations (GitHubRepository, GitHubIssue,
GitHubFile) that bridge raw GitHub REST API payloads to the intermediate Document
and OKF knowledge representation pipelines.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata


@dataclass
class GitHubFile:
    """Represents a single file inside a GitHub repository."""
    path: str                          # e.g. "README.md" or "src/main.py"
    content: Optional[str] = None      # Decoded text content (if fetched)
    language: Optional[str] = None     # Inferred language from extension
    size: int = 0
    sha: Optional[str] = None
    url: Optional[str] = None          # Raw/API URL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GitHubIssue:
    """
    Provider-canonical GitHub issue / pull request model.
    """
    number: int
    title: str
    state: str = "open"
    is_pull_request: bool = False
    body: Optional[str] = None
    author: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    comments: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    html_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GitHubRepository:
    """
    Provider-canonical GitHub repository model.

    Unifies repositories fetched from the GitHub REST API into a clean, strongly-typed
    structure with direct conversion to the system's intermediate Document format.
    """
    full_name: str                       # "owner/name"
    url: str
    description: Optional[str] = None
    private: bool = False
    default_branch: str = "main"
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    owner: Optional[str] = None
    license_name: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    clone_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    readme_content: Optional[str] = None
    issues: List[GitHubIssue] = field(default_factory=list)

    @classmethod
    def from_api(cls, repo: Dict[str, Any]) -> "GitHubRepository":
        """Builds a GitHubRepository from a raw GitHub REST API repository object."""
        owner = (repo.get("owner") or {}).get("login")
        lic = (repo.get("license") or {})
        return cls(
            full_name=repo.get("full_name") or repo.get("name") or "owner/repo",
            url=repo.get("html_url") or "",
            description=repo.get("description"),
            private=bool(repo.get("private", False)),
            default_branch=repo.get("default_branch") or "main",
            language=repo.get("language"),
            stars=repo.get("stargazers_count", 0) or 0,
            forks=repo.get("forks_count", 0) or 0,
            open_issues=repo.get("open_issues_count", 0) or 0,
            owner=owner,
            license_name=lic.get("spdx_id") or lic.get("name"),
            topics=repo.get("topics", []) or [],
            clone_url=repo.get("clone_url"),
            created_at=repo.get("created_at"),
            updated_at=repo.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["issues"] = [i.to_dict() for i in self.issues]
        return d

    def to_intermediate_document(self) -> Document:
        """
        Converts this canonical repository into the system's universal intermediate Document.
        Enables immediate reuse of OKF v0.2 bundle generation, chunking, and Vector/Graph indexing.
        """
        metadata = DocumentMetadata(
            id=self.full_name,
            title=self.full_name,
            source_platform="github",
            url=self.url,
            created_time=self.created_at,
            last_edited_time=self.updated_at,
            parent_type="organization" if self.owner else "user",
            parent_id=self.owner,
            created_by=self.owner,
            last_edited_by=self.owner,
            extra={
                "private": self.private,
                "description": self.description,
                "default_branch": self.default_branch,
                "language": self.language,
                "stars": self.stars,
                "forks": self.forks,
                "open_issues": self.open_issues,
                "license": self.license_name,
                "owner": self.owner,
                "clone_url": self.clone_url,
                "topics": self.topics,
            },
        )

        blocks: List[ContentBlock] = []

        # 1. Repository Overview Heading + description
        blocks.append(
            ContentBlock(
                id=f"{self.full_name}_overview",
                type=BlockType.HEADING,
                text="Repository Overview",
                properties={"level": 1},
            )
        )
        if self.description:
            blocks.append(
                ContentBlock(
                    id=f"{self.full_name}_desc",
                    type=BlockType.PARAGRAPH,
                    text=self.description,
                )
            )

        # 2. Metadata summary callout
        meta_lines = [
            f"**Owner:** {self.owner}",
            f"**Default Branch:** {self.default_branch}",
            f"**Primary Language:** {self.language or 'unknown'}",
            f"**Stars:** {self.stars} | **Forks:** {self.forks}",
            f"**Open Issues:** {self.open_issues}",
            f"**License:** {self.license_name or 'unknown'}",
            f"**URL:** {self.url}",
        ]
        if self.topics:
            meta_lines.append(f"**Topics:** {', '.join(self.topics)}")
        blocks.append(
            ContentBlock(
                id=f"{self.full_name}_meta",
                type=BlockType.CALLOUT,
                text="\n".join(meta_lines),
                properties={"icon": "📦"},
            )
        )

        # 3. README content
        if self.readme_content and self.readme_content.strip():
            blocks.append(
                ContentBlock(
                    id=f"{self.full_name}_readme_heading",
                    type=BlockType.HEADING,
                    text="README",
                    properties={"level": 1},
                )
            )
            blocks.append(
                ContentBlock(
                    id=f"{self.full_name}_readme",
                    type=BlockType.PARAGRAPH,
                    text=self.readme_content.strip(),
                )
            )

        # 4. Issues & Pull Requests
        if self.issues:
            blocks.append(
                ContentBlock(
                    id=f"{self.full_name}_issues_heading",
                    type=BlockType.HEADING,
                    text=f"Issues & Pull Requests ({len(self.issues)})",
                    properties={"level": 1},
                )
            )
            for issue in self.issues:
                kind = "Pull Request" if issue.is_pull_request else "Issue"
                head = ContentBlock(
                    id=f"{self.full_name}_issue_{issue.number}",
                    type=BlockType.HEADING_2,
                    text=f"{kind} #{issue.number}: {issue.title}",
                )
                parts = [f"State: {issue.state}"]
                if issue.labels:
                    parts.append(f"Labels: {', '.join(issue.labels)}")
                if issue.body:
                    parts.append(issue.body)
                if issue.author:
                    parts.append(f"Opened by: {issue.author}")
                head.children = [
                    ContentBlock(
                        id=f"{self.full_name}_issue_{issue.number}_p_{i}",
                        type=BlockType.PARAGRAPH,
                        text=p,
                    )
                    for i, p in enumerate(parts, 1)
                ]
                blocks.append(head)

        # 5. Structured repo metrics table (drives OKF structured_data extraction)
        blocks.append(
            ContentBlock(
                id=f"{self.full_name}_metrics",
                type=BlockType.DATABASE,
                text=f"Repository: {self.full_name} ({self.default_branch})",
                columns=["Owner", "Stars", "Forks", "Open Issues", "Language"],
                rows=[{
                    "id": self.full_name,
                    "data": {
                        "Owner": self.owner,
                        "Stars": self.stars,
                        "Forks": self.forks,
                        "Open Issues": self.open_issues,
                        "Language": self.language or "unknown",
                    },
                }],
                properties={"total_rows": 1},
            )
        )

        return Document(metadata=metadata, blocks=blocks)
