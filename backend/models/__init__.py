"""
Models package for Enterprise Knowledge Agent.
"""

from .document import Document, DocumentMetadata, ContentBlock, BlockType
from .okf import OKFConcept, OKFBundle, OKFSource, OKFActor, OKFPermissions
from .email import EmailDocument, EmailAttachment
from .github import GitHubRepository, GitHubIssue, GitHubFile
from .dropbox import DropboxFile, DropboxFolder, DropboxEntry

__all__ = [
    "Document",
    "DocumentMetadata",
    "ContentBlock",
    "BlockType",
    "OKFConcept",
    "OKFBundle",
    "OKFSource",
    "OKFActor",
    "OKFPermissions",
    "EmailDocument",
    "EmailAttachment",
    "GitHubRepository",
    "GitHubIssue",
    "GitHubFile",
    "DropboxFile",
    "DropboxFolder",
    "DropboxEntry",
]
