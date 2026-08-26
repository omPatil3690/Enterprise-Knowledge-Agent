"""
Gmail MIME & Payload Parser.

Recursively navigates complex nested MIME structures (multipart/alternative,
multipart/mixed, multipart/related), decodes URL-safe base64 payloads, extracts
headers, plain text, HTML, and attachment metadata, and returns clean EmailDocument objects.
"""

import base64
from html import unescape
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.models.email import EmailAttachment, EmailDocument


def decode_base64url(data: str) -> str:
    """
    Decodes a URL-safe base64 string from Gmail's API payload.
    Automatically handles missing padding and UTF-8 / fallback encodings.
    """
    if not data:
        return ""
    
    # Replace URL-safe characters and add padding
    clean_data = data.replace("-", "+").replace("_", "/")
    padding = len(clean_data) % 4
    if padding != 0:
        clean_data += "=" * (4 - padding)

    try:
        raw_bytes = base64.b64decode(clean_data)
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        try:
            return raw_bytes.decode("latin-1", errors="replace")
        except Exception:
            return ""


def clean_html_to_text(html_content: str) -> str:
    """
    Converts raw HTML email body into readable plain text by removing
    script/style tags, converting line breaks, and stripping remaining HTML tags.
    """
    if not html_content:
        return ""

    # Remove script and style elements
    text = re.sub(r"<(script|style).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace block level elements and breaks with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|h\d)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li.*?>", "\n• ", text, flags=re.IGNORECASE)
    
    # Strip remaining HTML tags
    text = re.sub(r"<.*?>", "", text)
    
    # Unescape HTML entities (&nbsp;, &amp;, &lt;, etc.)
    text = unescape(text)
    
    # Normalize multiple newlines and trailing whitespace
    lines = [line.strip() for line in text.splitlines()]
    clean_text = "\n".join(line for line in lines if line)
    return clean_text


def extract_headers_map(headers_list: List[Dict[str, str]]) -> Dict[str, str]:
    """Converts Gmail's list of {'name': ..., 'value': ...} into a case-insensitive lookup map."""
    headers = {}
    for h in headers_list:
        name = h.get("name", "").strip().lower()
        val = h.get("value", "").strip()
        if name:
            headers[name] = val
    return headers


def parse_recipients_list(header_val: Optional[str]) -> List[str]:
    """Splits comma-separated email recipient lists into clean individual strings."""
    if not header_val:
        return []
    # Split by comma but respect basic name formatting
    return [r.strip() for r in header_val.split(",") if r.strip()]


def _extract_mime_parts_recursive(part: Dict[str, Any]) -> Tuple[List[str], List[str], List[EmailAttachment]]:
    """
    Recursively traverses nested MIME parts (multipart/alternative, multipart/mixed).
    
    Returns:
        Tuple of (list_of_plain_texts, list_of_html_texts, list_of_attachments)
    """
    plain_texts: List[str] = []
    html_texts: List[str] = []
    attachments: List[EmailAttachment] = []

    mime_type = part.get("mimeType", "").lower()
    filename = part.get("filename", "").strip()
    body = part.get("body", {})
    data = body.get("data", "")
    att_id = body.get("attachmentId")
    size = body.get("size", 0)

    # 1. Check for File Attachment
    if filename or att_id or (mime_type.startswith(("application/", "image/", "audio/", "video/")) and mime_type not in ("application/json",)):
        header_map = extract_headers_map(part.get("headers", []))
        content_id = header_map.get("content-id")
        attachments.append(
            EmailAttachment(
                filename=filename or f"attachment_{len(attachments)+1}",
                mime_type=mime_type or "application/octet-stream",
                size_bytes=size,
                attachment_id=att_id,
                content_id=content_id,
            )
        )

    # 2. Text / HTML Leaf Parts
    elif mime_type == "text/plain" and data:
        decoded = decode_base64url(data)
        if decoded:
            plain_texts.append(decoded)

    elif mime_type == "text/html" and data:
        decoded = decode_base64url(data)
        if decoded:
            html_texts.append(decoded)

    # 3. Recurse into nested multipart containers
    for child in part.get("parts", []):
        c_plain, c_html, c_att = _extract_mime_parts_recursive(child)
        plain_texts.extend(c_plain)
        html_texts.extend(c_html)
        attachments.extend(c_att)

    return plain_texts, html_texts, attachments


def parse_gmail_message(raw_message: Dict[str, Any]) -> EmailDocument:
    """
    Parses a full Gmail API message dictionary (format='full') into a canonical EmailDocument.
    
    Args:
        raw_message: Raw dictionary returned from users().messages().get(..., format='full').

    Returns:
        Canonical EmailDocument object.
    """
    msg_id = raw_message.get("id", "")
    thread_id = raw_message.get("threadId", "")
    snippet = raw_message.get("snippet", "")
    labels = raw_message.get("labelIds", [])
    payload = raw_message.get("payload", {})

    # Extract Header fields
    headers = extract_headers_map(payload.get("headers", []))
    sender = headers.get("from", "Unknown Sender")
    recipients = parse_recipients_list(headers.get("to"))
    cc = parse_recipients_list(headers.get("cc"))
    bcc = parse_recipients_list(headers.get("bcc"))
    subject = headers.get("subject", "(No Subject)")
    date = headers.get("date")

    # Extract Body content and Attachments recursively
    plain_parts, html_parts, attachments = _extract_mime_parts_recursive(payload)

    # Combine Plain Text
    body_text = "\n\n".join(p.strip() for p in plain_parts if p.strip())
    
    # Combine HTML Body
    body_html = "\n".join(html_parts) if html_parts else None

    # Fallback: if no text/plain part was provided, convert HTML to clean text
    if not body_text and body_html:
        body_text = clean_html_to_text(body_html)

    # Final Fallback: use snippet if body is still empty
    if not body_text and snippet:
        body_text = snippet

    return EmailDocument(
        id=msg_id,
        thread_id=thread_id,
        sender=sender,
        recipients=recipients,
        cc=cc,
        bcc=bcc,
        subject=subject,
        date=date,
        body_text=body_text,
        body_html=body_html,
        snippet=snippet,
        labels=labels,
        attachments=attachments,
        source_platform="gmail"
    )


def parse_gmail_messages(raw_messages: List[Dict[str, Any]]) -> List[EmailDocument]:
    """Batch parses multiple raw Gmail messages into EmailDocument objects."""
    return [parse_gmail_message(msg) for msg in raw_messages if msg]
