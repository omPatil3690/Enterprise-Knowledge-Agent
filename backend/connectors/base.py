"""
Base Connector Interface for Enterprise Knowledge Agent.

All enterprise source connectors (Notion, Confluence, Jira, Slack, Drive, etc.)
must inherit from this base class to ensure consistent lifecycle management,
credential validation, full ingestion, and incremental synchronization.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from backend.models.document import Document


class BaseConnector(ABC):
    """
    Abstract Base Class for all Enterprise Data Source Connectors.
    """

    def __init__(self, name: str):
        """
        Initialize the base connector.
        
        Args:
            name: Identifier for the connector platform (e.g. 'notion', 'confluence', 'jira').
        """
        self.name = name

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Tests whether the connector can successfully authenticate and communicate
        with the underlying platform API.

        Returns:
            True if authentication and connection succeed, False otherwise.
        """
        pass

    @abstractmethod
    def load_documents(self) -> List[Document]:
        """
        Fetches and normalizes all accessible documents from the source platform
        into our standardized intermediate Document representation.

        Returns:
            List of normalized Document objects ready for OKF conversion and chunking.
        """
        pass

    @abstractmethod
    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches and normalizes a single document identified by its platform source ID.

        Args:
            doc_id: Unique identifier on the source platform (e.g. Notion page UUID).

        Returns:
            Normalized Document if found, None otherwise.
        """
        pass

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only documents that have been modified or created after `last_sync_time`.
        Default fallback implementation loads all documents if delta query is not overridden.

        Args:
            last_sync_time: ISO 8601 timestamp representing the previous sync time.

        Returns:
            List of newly modified or created Document objects.
        """
        # Default fallback: full load if platform does not support server-side delta filtering
        docs = self.load_documents()
        if not last_sync_time:
            return docs

        filtered_docs: List[Document] = []
        for doc in docs:
            edited = doc.metadata.last_edited_time
            if edited and edited > last_sync_time:
                filtered_docs.append(doc)
        return filtered_docs
