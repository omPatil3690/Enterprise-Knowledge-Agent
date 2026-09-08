"""
End-to-End Test Runner for Jira Connector.

Validates:
1. BaseConnector interface conformance
2. Basic-auth connection testing (test_connection)
3. Project auto-discovery and issue ingestion into Document format
4. ADF description parsing and Markdown rendering
"""

import argparse
import json
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

from backend.connectors.jira.connector import JiraConnector

SCRIPT_DIR = Path(__file__).resolve().parent
JIRA_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = JIRA_DIR / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_test(project_keys: str = "", include_projects: bool = False, max_issues: int = 100) -> None:
    print("\n" + "=" * 60)
    print("🚀 ENTERPRISE KNOWLEDGE AGENT - JIRA CONNECTOR RUNNER")
    print("=" * 60)

    # 1. Initialize Connector (picks up credentials from .env)
    keys = [k.strip() for k in project_keys.split(",") if k.strip()] if project_keys else []
    try:
        connector = JiraConnector(
            project_keys=keys,
            max_issues=max_issues,
            include_project_documents=include_projects,
        )
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return

    # 2. Test Connection
    print("📡 Testing API Connection to Jira...")
    if connector.test_connection():
        print("✅ Connection Successful! (Authenticated with Jira API)")
        user = connector.get_current_user()
        if user:
            print(f"   Authenticated as: {user.get('displayName') or user.get('name')} "
                  f"({user.get('emailAddress')})")
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
        safe_name = doc.metadata.title.replace("/", "_").replace("\\", "_").replace(":", "_").strip("_") or "root"
        json_filename = f"output_document_{safe_name}.json"
        json_path = TEST_DATA_DIR / json_filename
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)

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
                print(f"• Project Key:      {extra.get('project_key')}")
                print(f"• Issue Type:       {extra.get('issue_type')}")
                print(f"• Status:           {extra.get('status')}")

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
    parser = argparse.ArgumentParser(description="Run and test the Jira Connector")
    parser.add_argument(
        "--projects",
        type=str,
        default="",
        help="Comma-separated project keys to ingest (default '' = all projects)",
    )
    parser.add_argument(
        "--include-projects",
        action="store_true",
        help="Also generate a project-level overview Document per project",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=100,
        help="Maximum number of issues to fetch per project (default 100)",
    )
    args = parser.parse_args()

    run_test(
        project_keys=args.projects,
        include_projects=args.include_projects,
        max_issues=args.max_issues,
    )


if __name__ == "__main__":
    main()