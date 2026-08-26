"""
Email Connectors Package.
"""

from backend.models.email import EmailAttachment, EmailDocument
from backend.connectors.email.gmail.connector import GmailConnector
from backend.connectors.email.gmail.client import GmailClient

__all__ = ["EmailDocument", "EmailAttachment", "GmailConnector", "GmailClient"]
