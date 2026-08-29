"""
GitHub Connector Package.
"""

from .connector import GitHubConnector, dict_to_document
from .client import GitHubClient
from .parser import (
    normalize_repo_document,
    normalize_issue_document,
    normalize_repo_metadata,
    extract_issue_blocks,
)

__all__ = [
    "GitHubConnector",
    "GitHubClient",
    "dict_to_document",
    "normalize_repo_document",
    "normalize_issue_document",
    "normalize_repo_metadata",
    "extract_issue_blocks",
]
