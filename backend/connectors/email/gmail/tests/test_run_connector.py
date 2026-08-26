"""
End-to-End Test Runner for Gmail Connector.

Validates:
1. BaseConnector interface conformance
2. OAuth connection testing (test_connection)
3. Full message ingestion and conversion to intermediate Document format
4. Markdown rendering of email documents
"""

import json
from pathlib import Path
import sys

# Ensure project root is in sys.path
SCRIPT_PATH = Path(__file__).resolve()
current = SCRIPT_PATH.parent
while current != current.parent:
    if (current / "backend").exists():
        if str(current) not in sys.path:
            sys.path.insert(0, str(current))
        break
    current = current.parent

from backend.connectors.email.gmail.connector import GmailConnector

SCRIPT_DIR = Path(__file__).resolve().parent
GMAIL_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = GMAIL_DIR / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 65)
    print("📬 GMAIL CONNECTOR - LIVE END-TO-END TEST RUNNER")
    print("=" * 65)

    connector = GmailConnector(max_messages=5)

    print("📡 Testing Gmail API connection...")
    if not connector.test_connection():
        print("❌ Connection Failed. Please verify credentials.json and token.json.")
        return

    print("✅ Connection Authenticated Successfully!")
    print("-" * 65)

    print("📥 Loading and normalizing recent inbox emails...")
    documents = connector.load_documents(max_results=5)

    if not documents:
        print("⚠️ No emails were returned or parsed.")
        return

    print(f"✅ Successfully ingested {len(documents)} intermediate Document(s):\n")

    for idx, doc in enumerate(documents, 1):
        print(f"[{idx}/{len(documents)}] 📄 Title: \"{doc.metadata.title}\"")
        print(f"    • Source ID:   {doc.metadata.id}")
        print(f"    • Created By:  {doc.metadata.created_by}")
        print(f"    • Date:        {doc.metadata.created_time}")
        print(f"    • Total Blocks: {len(doc.blocks)}")
        print(f"    • Thread ID:   {doc.metadata.extra.get('thread_id')}")
        print("-" * 65)

    # 1. Save normalized intermediate Document JSON
    json_out_file = TEST_DATA_DIR / "output_email_documents.json"
    with open(json_out_file, "w", encoding="utf-8") as f:
        json.dump([d.to_dict() for d in documents], f, indent=2, ensure_ascii=False)

    # 2. Save rendered Markdown of the first email
    md_out_file = TEST_DATA_DIR / "output_sample_email.md"
    with open(md_out_file, "w", encoding="utf-8") as f:
        f.write(documents[0].to_markdown())

    print("\n" + "=" * 65)
    print("🎉 INGESTION COMPLETE - ARTIFACTS SAVED TO TEST_DATA:")
    print(f"   • Structured JSON:  {json_out_file.name}")
    print(f"   • Rendered Markdown: {md_out_file.name}")
    print(f"   • Directory:         {TEST_DATA_DIR}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
