"""
Canonical Email Models for Enterprise Knowledge Agent.

Defines provider-independent email representations (EmailDocument, EmailAttachment)
that bridge raw email API payloads (Gmail, Outlook, IMAP) to the intermediate Document
and OKF knowledge representation pipelines.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from backend.models.document import BlockType, ContentBlock, Document, DocumentMetadata


@dataclass
class EmailAttachment:
    """Represents a file or media attachment on an email."""
    filename: str
    mime_type: str
    size_bytes: int = 0
    attachment_id: Optional[str] = None
    content_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmailDocument:
    """
    Provider-independent canonical email model.
    
    Unifies emails extracted from Gmail, Outlook, IMAP, or EML files into a clean,
    strongly-typed structure with direct conversion to the system's intermediate Document format.
    """
    id: str                                      # Provider unique message ID
    thread_id: str                               # Conversation thread ID
    sender: str                                  # Sender header (e.g., "Jane Doe <jane@company.com>")
    recipients: List[str] = field(default_factory=list) # To recipients
    cc: List[str] = field(default_factory=list)         # Cc recipients
    bcc: List[str] = field(default_factory=list)        # Bcc recipients
    subject: str = "No Subject"                  # Email subject line
    date: Optional[str] = None                   # ISO 8601 or RFC 2822 timestamp
    body_text: str = ""                          # Extracted plain text content
    body_html: Optional[str] = None              # Raw / cleaned HTML content
    snippet: Optional[str] = None                # Short preview snippet
    labels: List[str] = field(default_factory=list) # Platform labels (e.g. INBOX, SENT, IMPORTANT)
    attachments: List[EmailAttachment] = field(default_factory=list)
    source_platform: str = "gmail"               # Source provider (gmail, outlook, imap)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes canonical email to a dictionary."""
        d = asdict(self)
        d["attachments"] = [a.to_dict() for a in self.attachments]
        return d

    def to_intermediate_document(self) -> Document:
        """
        Converts this canonical email into the system's universal intermediate Document format.
        Allows immediate reuse of OKF v0.2 bundle generation, chunking, and Vector/Graph indexing.
        """
        title = self.subject if self.subject.strip() else f"Email from {self.sender}"

        metadata = DocumentMetadata(
            id=self.id,
            title=title,
            source_platform=self.source_platform,
            url=f"{self.source_platform}://messages/{self.id}",
            created_time=self.date,
            last_edited_time=self.date,
            parent_type="thread",
            parent_id=self.thread_id,
            created_by=self.sender,
            extra={
                "thread_id": self.thread_id,
                "sender": self.sender,
                "recipients": self.recipients,
                "cc": self.cc,
                "labels": self.labels,
                "attachment_count": len(self.attachments),
                "attachment_names": [a.filename for a in self.attachments],
            }
        )

        blocks: List[ContentBlock] = []

        # 1. Header Summary Callout Block
        header_summary = (
            f"**From:** {self.sender}\n"
            f"**To:** {', '.join(self.recipients) if self.recipients else 'None'}\n"
        )
        if self.cc:
            header_summary += f"**Cc:** {', '.join(self.cc)}\n"
        if self.date:
            header_summary += f"**Date:** {self.date}\n"
        if self.labels:
            header_summary += f"**Labels:** {', '.join(self.labels)}\n"

        blocks.append(
            ContentBlock(
                id=f"{self.id}_headers",
                type=BlockType.CALLOUT,
                text=header_summary.strip(),
                properties={"icon": "✉️"}
            )
        )

        # 2. Email Subject as Heading
        blocks.append(
            ContentBlock(
                id=f"{self.id}_subject",
                type=BlockType.HEADING_2,
                text=self.subject
            )
        )

        # 3. Email Body Paragraphs
        body_content = self.body_text.strip() if self.body_text else (self.snippet or "")
        paragraphs = [p.strip() for p in body_content.split("\n\n") if p.strip()]

        for p_idx, para in enumerate(paragraphs, 1):
            blocks.append(
                ContentBlock(
                    id=f"{self.id}_p_{p_idx}",
                    type=BlockType.PARAGRAPH,
                    text=para
                )
            )

        # 4. Attachments (if any)
        if self.attachments:
            att_block = ContentBlock(
                id=f"{self.id}_attachments",
                type=BlockType.BULLETED_LIST_ITEM,
                text="**Attachments:**",
                children=[
                    ContentBlock(
                        id=f"{self.id}_att_{idx}",
                        type=BlockType.BULLETED_LIST_ITEM,
                        text=f"📎 `{att.filename}` ({att.mime_type}, {att.size_bytes} bytes)"
                    )
                    for idx, att in enumerate(self.attachments, 1)
                ]
            )
            blocks.append(att_block)

        return Document(metadata=metadata, blocks=blocks)
