"""
End-to-End Test Runner for Dropbox Connector.

Validates:
1. BaseConnector interface conformance
2. Token/OAuth connection testing (test_connection)
3. Folder/file listing and text-file ingestion into Document format
4. Markdown rendering of Dropbox documents
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Ensure project root is in sys.path
SCRIPT_PATH = Path(__file__).resolve()
current = SCRIPT_PATH.parent
while current != current.parent:
    if (current / "backend").exists():
        if str(current) not in sys.path:
            sys.path.insert(0, str(current))
        break
    current = current.parent

# Ensure .env is loaded
load_dotenv(find_dotenv())

from backend.connectors.dropbox.connector import DropboxConnector

SCRIPT_DIR = Path(__file__).resolve().parent
DROPBOX_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = DROPBOX_DIR / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_test(path: str = "", no_folders: bool = False, no_files: bool = False, max_files: int = 200) -> None:
    print("\n" + "=" * 60)
    print("🚀 ENTERPRISE KNOWLEDGE AGENT - DROPBOX CONNECTOR RUNNER")
    print("=" * 60)

    # 1. Initialize Connector (picks up credentials from .env)
    try:
        connector = DropboxConnector(
            root_path=path,
            include_folders=not no_folders,
            include_files=not no_files,
            max_files=max_files,
        )
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return

    # 2. Test Connection
    print("📡 Testing API Connection to Dropbox...")
    if connector.test_connection():
        print("✅ Connection Successful! (Authenticated with Dropbox API)")
        account = connector.client.get_current_account()
        if account:
            print(f"   Account: {account.get('display_name')} ({account.get('email')})")
    else:
        print("❌ Connection Failed. Please check your credentials in .env.")
        return

    print("-" * 60)

    # 3. Ingest Documents
    docs = connector.load_documents()

    if not docs:
        print("⚠️ No documents were returned or parsed.")
        return

    print(f"\n🎉 Successfully ingested {len(docs)} document(s)!")

    # 4. Display and Save Details for each document
    for idx, doc in enumerate(docs, 1):
        # Save JSON output for all documents
        safe_name = doc.metadata.title.replace("/", "_").replace("\\", "_").strip("_") or "root"
        json_filename = f"output_document_{safe_name}.json"
        json_path = TEST_DATA_DIR / json_filename
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)

        # Save Markdown output for all documents
        md_filename = f"output_document_{safe_name}.md"
        md_path = TEST_DATA_DIR / md_filename
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(doc.to_markdown())

        if idx <= 5:
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
            extra = doc.metadata.extra
            if extra:
                print(f"• Kind:             {extra.get('kind')}")
                if extra.get("size") is not None:
                    print(f"• Size:             {extra.get('size')} bytes")

            # Block types breakdown
            types_count = {}
            for b in doc.blocks:
                t = b.type.value if hasattr(b.type, "value") else str(b.type)
                types_count[t] = types_count.get(t, 0) + 1
            print(f"• Block Breakdown:  {types_count}")
            print(f"💾 Saved structured JSON to:   {json_path.name}")
            print(f"💾 Saved rendered Markdown to: {md_path.name}")
        elif idx == 6:
            print(f"\n... (remaining {len(docs) - 5} documents saved silently to {TEST_DATA_DIR.name}/) ...")

    print("\n" + "=" * 60)
    print("✨ Ingestion & Normalization verification complete!")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and test the Dropbox Connector")
    parser.add_argument(
        "--path",
        type=str,
        default="",
        help="Dropbox root path to walk (default '' = whole account)",
    )
    parser.add_argument(
        "--no-folders",
        action="store_true",
        help="Skip folder documents",
    )
    parser.add_argument(
        "--no-files",
        action="store_true",
        help="Skip text file downloads",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Max number of text files to download (default 200)",
    )
    args = parser.parse_args()

    run_test(
        path=args.path,
        no_folders=args.no_folders,
        no_files=args.no_files,
        max_files=args.max_files,
    )


if __name__ == "__main__":
    main()
