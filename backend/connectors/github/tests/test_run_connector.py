"""
End-to-End Test Runner for GitHub Connector.

Validates:
1. BaseConnector interface conformance
2. Token connection testing (test_connection)
3. Repository ingestion and conversion to intermediate Document format
4. Markdown rendering of GitHub repository documents
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Ensure project root is in sys.path so 'backend' package imports work cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure .env is loaded
load_dotenv(find_dotenv())

from backend.connectors.github.connector import GitHubConnector

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_test(repos: list = None, auto_discover: bool = True, no_readme: bool = False, no_issues: bool = False) -> None:
    token = os.getenv("GITHUB_TOKEN")

    print("\n" + "=" * 60)
    print("🚀 ENTERPRISE KNOWLEDGE AGENT - GITHUB CONNECTOR RUNNER")
    print("=" * 60)

    if not token:
        print("❌ ERROR: GITHUB_TOKEN is not set in your .env file.")
        return

    print(f"🔑 Token: {token[:8]}... (detected)")
    print(f"🔍 Auto-Discovery Mode: {auto_discover}")
    print(f"📚 Include Repos: {repos or '(auto-discover all)'}")
    print(f"📄 Fetch README: {not no_readme} | Fetch Issues: {not no_issues}")
    print("-" * 60)

    # 1. Initialize Connector
    connector = GitHubConnector(
        token=token,
        include_repos=repos,
        fetch_readme=not no_readme,
        fetch_issues=not no_issues,
    )

    # 2. Test Connection
    print("📡 Testing API Connection to GitHub...")
    if connector.test_connection():
        print("✅ Connection Successful! (Authenticated with GitHub API)")
        user = connector.client.get_current_user()
        if user:
            print(f"   Authenticated as: {user.get('login')} ({user.get('name') or 'no display name'})")
    else:
        print("❌ Connection Failed. Please check your GITHUB_TOKEN in .env.")
        return

    print("-" * 60)

    # 3. Ingest Documents
    if repos:
        print(f"📥 Ingesting explicit repos: {repos}...")
    else:
        print("🌐 Discovering and loading all accessible repositories...")
    docs = connector.load_documents(include_repos=repos or None)

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
        print(f"• Created By:       {doc.metadata.created_by or 'N/A'}")
        print(f"• Last Edited By:   {doc.metadata.last_edited_by or 'N/A'}")
        print(f"• Parent Type:      {doc.metadata.parent_type or 'N/A'}")
        print(f"• Parent ID:        {doc.metadata.parent_id or 'N/A'}")
        print(f"• Total Root Blocks:{len(doc.blocks)}")
        extra = doc.metadata.extra
        if extra:
            print(f"• Private:          {extra.get('private')}")
            print(f"• Stars / Forks:    {extra.get('stars')} / {extra.get('forks')}")
            print(f"• Open Issues:      {extra.get('open_issues')}")
            print(f"• Default Branch:   {extra.get('default_branch')}")

        # Block types breakdown
        types_count = {}
        for b in doc.blocks:
            t = b.type.value if hasattr(b.type, "value") else str(b.type)
            types_count[t] = types_count.get(t, 0) + 1
        print(f"• Block Breakdown:  {types_count}")

        # Save JSON output
        safe_name = doc.metadata.title.replace("/", "_")
        json_filename = f"output_document_{safe_name}.json" if len(docs) > 1 else "output_document.json"
        json_path = TEST_DATA_DIR / json_filename
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved structured JSON to:   {json_path}")

        # Save Markdown output
        md_filename = f"output_document_{safe_name}.md" if len(docs) > 1 else "output_document.md"
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
    parser = argparse.ArgumentParser(description="Run and test the GitHub Connector")
    parser.add_argument(
        "--repo",
        action="append",
        default=None,
        help="Explicit 'owner/repo' to ingest. Repeat for multiple repos. "
             "Defaults to auto-discovery of all repos if omitted.",
    )
    parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip README fetching (faster, fewer API calls)",
    )
    parser.add_argument(
        "--no-issues",
        action="store_true",
        help="Skip issues/PR fetching",
    )
    args = parser.parse_args()

    auto_discover = not args.repo
    run_test(repos=args.repo, auto_discover=auto_discover, no_readme=args.no_readme, no_issues=args.no_issues)


if __name__ == "__main__":
    main()
