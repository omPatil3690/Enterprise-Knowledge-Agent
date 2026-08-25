"""
Test suite for Gmail MIME and Payload Parser.

Tests parsing of real/synthetic Gmail JSON message payloads from test_data/
and validates conversion into canonical EmailDocument and universal Document formats.
"""

import json
from pathlib import Path
import sys

# Ensure project root is in sys.path
SCRIPT_PATH = Path(__file__).resolve()
# Find project root containing 'backend' folder
current = SCRIPT_PATH.parent
while current != current.parent:
    if (current / "backend").exists():
        if str(current) not in sys.path:
            sys.path.insert(0, str(current))
        break
    current = current.parent

from backend.connectors.email.gmail.parser import parse_gmail_message, parse_gmail_messages
from backend.models.email import EmailDocument

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"


def test_parser():
    print("=" * 65)
    print("🧪 TESTING GMAIL MIME & PAYLOAD PARSER")
    print("=" * 65)

    sample_file = TEST_DATA_DIR / "all_sample_messages.json"
    if not sample_file.exists():
        print(f"⚠️ Test data not found at {sample_file}.")
        print("Run test_gmail.py first to fetch sample payloads.")
        return

    with open(sample_file, "r", encoding="utf-8") as f:
        raw_messages = json.load(f)

    print(f"📦 Loaded {len(raw_messages)} raw Gmail payload(s) from test_data/.")

    email_docs = parse_gmail_messages(raw_messages)

    print(f"✅ Successfully parsed {len(email_docs)} EmailDocument(s):\n")
    print(type(email_docs[0]), end="\n")
    for idx, doc in enumerate(email_docs, 1):
        print(f"[{idx}/{len(email_docs)}] ✉️ ID: {doc.id}")
        print(f"    • Subject:      {doc.subject}")
        print(f"    • Sender:       {doc.sender}")
        print(f"    • Recipients:   {doc.recipients}")
        print(f"    • Date:         {doc.date}")
        print(f"    • Body Length:  {len(doc.body_text)} chars")
        print(f"    • Attachments:  {len(doc.attachments)}")
        if doc.attachments:
            for att in doc.attachments:
                print(f"       📎 {att.filename} ({att.mime_type}, {att.size_bytes} bytes)")

        # Verify conversion to universal Intermediate Document
        intermediate_doc = doc.to_intermediate_document()
        print(f"    • Intermediate Blocks: {len(intermediate_doc.blocks)} blocks generated")
        print("-" * 65)

    # Save parsed output for inspection
    out_file = TEST_DATA_DIR / "parsed_email_documents.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([d.to_dict() for d in email_docs], f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Parsed EmailDocument batch saved to: {out_file.name}")


if __name__ == "__main__":
    test_parser()
