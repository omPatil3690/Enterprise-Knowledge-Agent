"""
GitHub Connector Orchestrator.

Implements BaseConnector to provide a unified interface for:
- Testing GitHub credentials and reachability
- Repository auto-discovery and metadata
- Full repo + issues ingestion into typed Document objects
- Single issue/PR loading by number
- Incremental synchronization based on updated timestamps
"""

import os
from typing import Any, Dict, List, Optional

from backend.connectors.base import BaseConnector
from backend.connectors.github.client import GitHubClient
from backend.connectors.github.parser import (
    normalize_issue_document,
    normalize_repo_document,
)
from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata
from backend.models.github import GitHubIssue, GitHubRepository


def dict_to_content_block(data: Dict[str, Any], parent_id: Optional[str] = None) -> ContentBlock:
    """
    Recursively converts a normalized block dictionary into a typed ContentBlock object,
    preserving code language, heading levels, and nested children.
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
        source_platform=doc_dict.get("source", "github"),
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


class GitHubConnector(BaseConnector):
    """
    Enterprise Connector for GitHub repositories, issues, and pull requests.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        include_repos: Optional[List[str]] = None,
        fetch_readme: bool = True,
        fetch_issues: bool = True,
    ):
        """
        Initialize the GitHub Connector.

        Args:
            token: GitHub Personal Access Token (defaults to GITHUB_TOKEN in .env).
            include_repos: Optional list of "owner/repo" strings to load. If empty,
                           auto-discovers all repos accessible to the token.
            fetch_readme: If True, fetches and includes each repo's README when present.
            fetch_issues: If True, fetches and includes open issues/PRs for each repo.
        """
        super().__init__(name="github")
        self.include_repos = include_repos or []
        self.fetch_readme = fetch_readme
        self.fetch_issues = fetch_issues
        self.client = GitHubClient(token=token)

    def test_connection(self) -> bool:
        """Validates GitHub token credentials and API reachability."""
        return self.client.test_connection()

    def load_repo_by_name(self, full_name: str) -> Optional[Document]:
        """
        Loads a single repository as a normalized Document.

        Args:
            full_name: 'owner/repo' string identifying the repository.

        Returns:
            Typed Document object or None if failed.
        """
        try:
            owner, _, repo_name = full_name.partition("/")
            if not owner or not repo_name:
                print(f"⚠️ Invalid repo name: {full_name}. Expected 'owner/repo'.")
                return None

            repo = self.client.get_repo(owner, repo_name)
            if not repo:
                print(f"⚠️ Repository {full_name} not found or inaccessible.")
                return None

            readme_content: Optional[str] = None
            issues: Optional[List[Dict[str, Any]]] = None

            if self.fetch_readme:
                readme_file = self.client.get_file_content(owner, repo_name, "README.md")
                readme_content = (readme_file or {}).get("content")

            if self.fetch_issues:
                issues = self.client.list_issues(owner, repo_name, state="open")

            # Canonical model path: GitHubRepository -> to_intermediate_document()
            repository = GitHubRepository.from_api(repo)
            repository.readme_content = readme_content
            if issues:
                repository.issues = [
                    GitHubIssue(
                        number=issue.get("number", 0),
                        title=issue.get("title") or "Untitled",
                        state=issue.get("state", "open"),
                        is_pull_request="pull_request" in issue,
                        body=issue.get("body"),
                        author=(issue.get("user") or {}).get("login"),
                        labels=[l.get("name") for l in issue.get("labels", []) if l.get("name")],
                        comments=issue.get("comments", 0),
                        created_at=issue.get("created_at"),
                        updated_at=issue.get("updated_at"),
                        html_url=issue.get("html_url"),
                    )
                    for issue in issues
                ]
            return repository.to_intermediate_document()
        except Exception as e:
            print(f"⚠️ Error loading GitHub repository {full_name}: {e}")
            return None

    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches and normalizes a single GitHub resource.

        Args:
            doc_id: Either 'owner/repo' for a repository, or 'owner/repo#<issue_number>'
                    for a specific issue or pull request.

        Returns:
            Typed Document object or None if failed.
        """
        if "#" in doc_id:
            full_name, _, num_str = doc_id.rpartition("#")
            return self.load_issue_by_id(full_name, num_str)
        return self.load_repo_by_name(doc_id)

    def load_issue_by_id(self, full_name: str, issue_number: str) -> Optional[Document]:
        """
        Loads a single issue or pull request as a normalized Document.

        Args:
            full_name: 'owner/repo' string.
            issue_number: Issue or PR number.

        Returns:
            Typed Document object or None if failed.
        """
        try:
            owner, _, repo_name = full_name.partition("/")
            repo = self.client.get_repo(owner, repo_name)
            if not repo:
                print(f"⚠️ Repository {full_name} not found or inaccessible.")
                return None

            url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}"
            response = self.client.session.get(url)
            if response.status_code != 200:
                print(f"⚠️ Issue {full_name}#{issue_number} not found.")
                return None

            issue = response.json()
            normalized = normalize_issue_document(issue, repo)
            return dict_to_document(normalized)
        except Exception as e:
            print(f"⚠️ Error loading GitHub issue {full_name}#{issue_number}: {e}")
            return None

    def load_documents(
        self,
        include_repos: Optional[List[str]] = None,
        fetch_readme: Optional[bool] = None,
        fetch_issues: Optional[bool] = None,
    ) -> List[Document]:
        """
        Loads documents from GitHub.
        - If include_repos is provided, loads those specific repos.
        - Otherwise, auto-discovers all repositories accessible to the token.

        Args:
            include_repos: Optional explicit list of 'owner/repo' strings.
            fetch_readme: Override for README fetching.
            fetch_issues: Override for issues fetching.

        Returns:
            List of typed Document objects ready for OKF conversion and chunking.
        """
        targets = include_repos if include_repos is not None else self.include_repos
        fetch_readme_override = fetch_readme if fetch_readme is not None else self.fetch_readme
        fetch_issues_override = fetch_issues if fetch_issues is not None else self.fetch_issues

        documents: List[Document] = []

        repo_names: List[str] = []
        if targets:
            repo_names = list(targets)
        else:
            print("🌐 Auto-discovering accessible repositories...")
            repos = self.client.list_repos()
            repo_names = [
                repo.get("full_name")
                for repo in repos
                if repo.get("full_name")
            ]

        # Temporarily apply overrides so load_repo_by_name picks them up
        prev_readme = self.fetch_readme
        prev_issues = self.fetch_issues
        self.fetch_readme = fetch_readme_override
        self.fetch_issues = fetch_issues_override
        try:
            for full_name in repo_names:
                doc = self.load_repo_by_name(full_name)
                if doc:
                    documents.append(doc)
        finally:
            self.fetch_readme = prev_readme
            self.fetch_issues = prev_issues

        return documents

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only repositories or issues updated after `last_sync_time`.

        Args:
            last_sync_time: ISO 8601 timestamp representing the previous sync time.

        Returns:
            List of newly modified or created Document objects.
        """
        if not last_sync_time:
            return self.load_documents()

        documents: List[Document] = []
        for full_name in self.include_repos or [r.get("full_name") for r in self.client.list_repos()]:
            if not full_name:
                continue
            doc = self.load_document_by_id(full_name)
            if not doc:
                continue
            edited = doc.metadata.last_edited_time
            if edited and edited > last_sync_time:
                documents.append(doc)
        return documents
