"""
Jira Connector Orchestrator.

Implements BaseConnector to provide a unified interface for:
- Testing Jira credentials and reachability
- Project auto-discovery across the site
- Single issue loading by key
- Full issue + ADF description extraction into typed Document objects
- Incremental synchronization based on update timestamps
"""

from typing import Any, Dict, List, Optional

from backend.connectors.base import BaseConnector
from backend.connectors.jira.client import JiraClient
from backend.connectors.jira.parser import (
    normalize_issue_document,
    normalize_project_document,
)
from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata


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
        source_platform=doc_dict.get("source", "jira"),
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


class JiraConnector(BaseConnector):
    """
    Enterprise Connector for Jira Projects, Issues, Epics, and Sprint Work.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        project_keys: Optional[List[str]] = None,
        jql: Optional[str] = None,
        max_issues: int = 500,
        include_project_documents: bool = False,
    ):
        """
        Initialize the Jira Connector.

        Args:
            url: Jira base URL (defaults to JIRA_URL in .env).
            username: Account e-mail address (defaults to JIRA_USERNAME in .env).
            api_token: Atlassian API token (defaults to JIRA_API_TOKEN in .env).
            project_keys: Optional list of project keys to load. If empty,
                          auto-discovers all projects visible to the account.
            jql: Optional raw JQL. If provided it overrides project filtering.
            max_issues: Maximum number of issues to fetch (per project, unless jql).
            include_project_documents: If True, additionally produces one Document per Project.
        """
        super().__init__(name="jira")
        self.project_keys = project_keys or []
        self.jql = jql or None
        self.max_issues = max_issues
        self.include_project_documents = include_project_documents
        self.client = JiraClient(url=url, username=username, api_token=api_token)

    def test_connection(self) -> bool:
        """Validates Jira credentials and API reachability."""
        return self.client.test_connection()

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Returns the authenticated Jira account metadata."""
        return self.client.get_current_user()

    def list_projects(self) -> List[Dict[str, Any]]:
        """Lists all projects visible to the authenticated account."""
        return self.client.list_projects()

    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches, extracts, and normalizes a single Jira issue.

        Args:
            doc_id: Jira issue key (e.g. 'ENG-123').

        Returns:
            Typed Document object or None if failed.
        """
        try:
            issue = self.client.get_issue(doc_id)
            if not issue:
                return None
            return dict_to_document(normalize_issue_document(issue))
        except Exception as e:
            print(f"⚠️ Error loading Jira issue {doc_id}: {e}")
            return None

    def load_project_document(self, project_key: str) -> Optional[Document]:
        """
        Produces a single Project-level Document (overview + metadata table).

        Args:
            project_key: Jira project key.

        Returns:
            Typed Document object or None if the project is inaccessible.
        """
        try:
            project = self.client.get_project(project_key)
            if not project:
                return None
            return dict_to_document(normalize_project_document(project))
        except Exception as e:
            print(f"⚠️ Error loading Jira project {project_key}: {e}")
            return None

    def load_issues_by_project(self, project_key: str) -> List[Document]:
        """Loads all issues inside a single Jira project."""
        documents: List[Document] = []
        issues = self.client.search_issues(
            project_key=project_key,
            max_results=self.max_issues,
        )
        for issue in issues:
            key = issue.get("key")
            if key:
                doc = self.load_document_by_id(key)
                if doc:
                    documents.append(doc)
        return documents

    def load_documents(self) -> List[Document]:
        """
        Loads accessible documents from Jira.
        - Auto-discovers projects (or uses project_keys filter).
        - Optionally produces Project-level documents.
        - Loads every issue within each project (or the provided JQL).

        Returns:
            List of typed Document objects ready for OKF conversion and chunking.
        """
        documents: List[Document] = []

        if self.jql:
            print(f"🔎 Running JQL search: {self.jql}")
            issues = self.client.search_issues(jql=self.jql, max_results=self.max_issues)
            for issue in issues:
                key = issue.get("key")
                if key:
                    doc = self.load_document_by_id(key)
                    if doc:
                        documents.append(doc)
            print(f"📋 Loaded {len(documents)} issue(s) from JQL search.")
            return documents

        projects = self.client.list_projects()
        if not projects:
            print("⚠️ No Jira projects found or accessible.")
            return documents

        projects = [p for p in projects if not self.project_keys or p.get("key") in self.project_keys]
        print(f"📚 Found {len(projects)} Jira project(s).")

        for project in projects:
            key = project.get("key") or ""
            project_docs: List[Document] = []

            if self.include_project_documents:
                project_doc = dict_to_document(normalize_project_document(project))
                if project_doc:
                    project_docs.append(project_doc)

            project_issues = self.load_issues_by_project(key)
            project_docs.extend(project_issues)
            documents.extend(project_docs)

            print(f"  → {project.get('name') or key}: {len(project_issues)} issue(s) "
                  f"{f'+ 1 project overview' if self.include_project_documents else ''}.")

        return documents

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only issues updated after `last_sync_time`.

        Args:
            last_sync_time: ISO 8601 timestamp representing the previous sync time.

        Returns:
            List of newly modified or created Document objects.
        """
        if not last_sync_time:
            return self.load_documents()

        documents: List[Document] = []
        if self.jql:
            issues = self.client.search_issues(jql=self.jql, max_results=self.max_issues)
        else:
            issues = []
            projects = self.client.list_projects()
            for project in projects:
                key = project.get("key") or ""
                if self.project_keys and key not in self.project_keys:
                    continue
                issues.extend(self.client.search_issues(project_key=key, max_results=self.max_issues))

        for issue in issues:
            fields = issue.get("fields") or {}
            updated = fields.get("updated")
            if updated and updated > last_sync_time:
                key = issue.get("key")
                if key:
                    doc = self.load_document_by_id(key)
                    if doc:
                        documents.append(doc)
        return documents