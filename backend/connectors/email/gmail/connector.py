"""
Gmail Connector Implementation.

Orchestrates GmailClient, MIME parser, and Document normalization to provide
a unified interface conforming to BaseConnector.
"""

from datetime import datetime
from typing import List, Optional

from backend.connectors.base import BaseConnector
from backend.connectors.email.gmail.client import GmailClient
from backend.connectors.email.gmail.parser import parse_gmail_message, parse_gmail_messages
from backend.models.document import Document
from backend.models.email import EmailDocument


class GmailConnector(BaseConnector):
    """
    Enterprise connector for Google Gmail.
    
    Provides:
    - OAuth 2.0 connection verification (test_connection)
    - Full inbox / search-based message ingestion (load_documents)
    - Single message lookup by ID (load_document_by_id)
    - Incremental synchronization via query timestamp filtering (sync_incremental)
    """

    def __init__(
        self,
        token_path: Optional[str] = None,
        credentials_path: Optional[str] = None,
        default_query: str = "label:INBOX",
        max_messages: int = 50,
    ):
        """
        Initialize the Gmail connector.
        
        Args:
            token_path: Optional custom path to token.json.
            credentials_path: Optional custom path to credentials.json.
            default_query: Default search filter for message ingestion (e.g. 'label:INBOX').
            max_messages: Maximum messages to retrieve during load_documents (default 50).
        """
        super().__init__(name="gmail")
        self.default_query = default_query
        self.max_messages = max_messages
        self.client = GmailClient(token_path=token_path, credentials_path=credentials_path)

    def test_connection(self) -> bool:
        """
        Validates Gmail OAuth credentials and user mailbox reachability.
        
        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        return self.client.test_connection()

    def load_documents(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Document]:
        """
        Retrieves, parses, and normalizes email messages from Gmail into standard Document objects.
        
        Args:
            query: Custom search query string (defaults to self.default_query).
            max_results: Max messages to retrieve (defaults to self.max_messages).

        Returns:
            List of normalized Document objects ready for OKF conversion and chunking.
        """
        search_query = query if query is not None else self.default_query
        limit = max_results or self.max_messages

        raw_messages = self.client.fetch_messages_batch(query=search_query, limit=limit)
        if not raw_messages:
            return []

        email_docs: List[EmailDocument] = parse_gmail_messages(raw_messages)
        return [e.to_intermediate_document() for e in email_docs]

    def load_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        Fetches and normalizes a single email message by its Gmail message ID.
        
        Args:
            doc_id: Gmail message ID.

        Returns:
            Normalized Document if found, None otherwise.
        """
        try:
            raw_message = self.client.get_message(doc_id, format="full")
            if not raw_message:
                return None
            email_doc = parse_gmail_message(raw_message)
            return email_doc.to_intermediate_document()
        except Exception as e:
            print(f"⚠️ Error loading Gmail document {doc_id}: {e}")
            return None

    def sync_incremental(self, last_sync_time: Optional[str] = None) -> List[Document]:
        """
        Fetches only emails that were received after `last_sync_time`.
        Leverages Gmail's native `after:YYYY/MM/DD` search query when possible.
        
        Args:
            last_sync_time: ISO 8601 or date string (e.g. '2026-08-20' or '2026-08-20T12:00:00Z').

        Returns:
            List of newly received Document objects.
        """
        if not last_sync_time:
            return self.load_documents()

        # Build server-side query filter if date format is parseable
        query = self.default_query
        try:
            # Parse ISO or standard date formats
            clean_date = last_sync_time.split("T")[0].replace("-", "/")
            query = f"{self.default_query} after:{clean_date}"
        except Exception:
            pass

        return self.load_documents(query=query)
