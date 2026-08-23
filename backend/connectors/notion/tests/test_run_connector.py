"""
End-to-End Notion Connector Runner & Tester.

Tests NotionConnector against a live Notion page or workspace and outputs:
1. Connection status
2. Extracted page metadata
3. Structured content blocks summary
4. Rendered Markdown view
5. Complete JSON representation saved to test_data/output_document.json
6. Rendered Markdown saved to test_data/output_document.md
"""

import argparse
import json
import os
from pathlib import Path
import sys
from dotenv import find_dotenv, load_dotenv

# Ensure project root is in sys.path so 'backend' package imports work cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure .env is loaded
load_dotenv(find_dotenv())

from backend.connectors.notion.connector import NotionConnector
from backend.models.document import Document

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_test(page_id: str = None, auto_discover: bool = False) -> None:
    token = os.getenv("NOTION_TOKEN")
    target_page_id = page_id or os.getenv("NOTION_PAGE_ID")

    print("\n" + "=" * 60)
    print("🚀 ENTERPRISE KNOWLEDGE AGENT - NOTION CONNECTOR RUNNER")
    print("=" * 60)

    if not token:
        print("❌ ERROR: NOTION_TOKEN is not set in your .env file.")
        return

    print(f"🔑 Token: {token[:8]}... (detected)")
    if target_page_id:
        print(f"📄 Target Page ID: {target_page_id}")
    print(f"🔍 Auto-Discovery Mode: {auto_discover}")
    print("-" * 60)

    # 1. Initialize Connector
    connector = NotionConnector(token=token, default_page_id=target_page_id)

    # 2. Test Connection
    print("📡 Testing API Connection to Notion...")
    if connector.test_connection():
        print("✅ Connection Successful! (Authenticated with Notion API)")
    else:
        print("❌ Connection Failed. Please check your NOTION_TOKEN in .env.")
        return

    print("-" * 60)

    # 3. Ingest Documents
    docs = []
    if auto_discover:
        print("🌐 Discovering and loading all accessible pages in workspace...")
        docs = connector.load_documents(auto_discover=True)
    elif target_page_id:
        print(f"📥 Ingesting page: {target_page_id}...")
        doc = connector.load_document_by_id(target_page_id)
        if doc:
            docs.append(doc)
    else:
        print("❌ ERROR: Please specify a --page-id or set NOTION_PAGE_ID in your .env file.")
        return

    if not docs:
        print("⚠️ No documents were returned or parsed.")
        return

    print(f"\n🎉 Successfully ingested {len(docs)} document(s)!")

    # 4. Display and Save Details for each document
    for idx, doc in enumerate(docs, 1):
        print("\n" + "=" * 60)
        print(f"📄 DOCUMENT #{idx}: {doc.metadata.title}")
        print("=" * 60)
        print(f"• ID:               {doc.metadata.id}")
        print(f"• Platform:         {doc.metadata.source_platform}")
        print(f"• URL:              {doc.metadata.url or 'N/A'}")
        print(f"• Created Time:     {doc.metadata.created_time or 'N/A'}")
        print(f"• Last Edited Time: {doc.metadata.last_edited_time or 'N/A'}")
        print(f"• Parent Type:      {doc.metadata.parent_type or 'N/A'}")
        print(f"• Parent ID:        {doc.metadata.parent_id or 'N/A'}")
        print(f"• Total Root Blocks:{len(doc.blocks)}")

        # Block types breakdown
        types_count = {}
        for b in doc.blocks:
            t = b.type.value if hasattr(b.type, "value") else str(b.type)
            types_count[t] = types_count.get(t, 0) + 1
        print(f"• Block Breakdown:  {types_count}")

        # Save JSON output
        json_filename = f"output_document_{doc.metadata.id}.json" if len(docs) > 1 else "output_document.json"
        json_path = TEST_DATA_DIR / json_filename
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved structured JSON to:   {json_path}")

        # Save Markdown output
        md_filename = f"output_document_{doc.metadata.id}.md" if len(docs) > 1 else "output_document.md"
        md_path = TEST_DATA_DIR / md_filename
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(doc.to_markdown())
        print(f"💾 Saved rendered Markdown to: {md_path}")

        # Print Markdown Preview
        print("\n" + "-" * 60)
        print("📝 RENDERED MARKDOWN PREVIEW:")
        print("-" * 60)
        md_content = doc.to_markdown()
        lines = md_content.splitlines()
        preview_lines = lines[:25]
        print("\n".join(preview_lines))
        if len(lines) > 25:
            print(f"\n... [{len(lines) - 25} more lines in {md_filename}] ...")

    print("\n" + "=" * 60)
    print("✨ Ingestion & Normalization verification complete!")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and test the Notion Connector")
    parser.add_argument(
        "--page-id",
        type=str,
        default=None,
        help="Optional Notion Page ID (defaults to NOTION_PAGE_ID in .env)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Auto-discover and ingest all pages in the workspace",
    )
    args = parser.parse_args()
    run_test(page_id=args.page_id, auto_discover=args.all)


if __name__ == "__main__":
    main()
