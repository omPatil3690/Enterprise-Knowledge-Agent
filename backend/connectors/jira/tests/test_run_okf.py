"""
End-to-End OKF v0.2 Knowledge Bundle Generator for Jira.

Ingests Jira projects/issues, converts them into standard OKF v0.2 Concepts,
and builds a complete Knowledge Bundle with:
- <issue_slug>.okf.md (YAML Frontmatter + Markdown Body + Footnote Citations)
- <issue_slug>.okf.json (Complete JSON metadata & structured records)
- index.md (Bundle directory listing for progressive disclosure)
- log.md (Chronological update history log)
"""

import argparse
import json
import re
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

load_dotenv(find_dotenv())

from backend.connectors.jira.connector import JiraConnector
from backend.models.okf import OKFBundle, OKFConcept, OKFPermissions

SCRIPT_DIR = Path(__file__).resolve().parent
JIRA_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = JIRA_DIR / "test_data"
BUNDLE_DIR = TEST_DATA_DIR / "okf_bundle"
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Converts an issue title into a clean filename slug."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)[:60] or "jira_issue"


def run_okf_bundle_generator(
    project_keys: str = "",
    include_projects: bool = False,
    max_issues: int = 100,
) -> None:
    print("\n" + "=" * 65)
    print("📦 JIRA CONNECTOR - OKF v0.2 KNOWLEDGE BUNDLE GENERATOR")
    print("=" * 65)

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

    print("📡 Connecting to Jira API...")
    user = None
    if connector.test_connection():
        user = connector.get_current_user()
        if user:
            print(f"✅ Connection Authenticated as: {user.get('displayName') or user.get('name')} "
                  f"({user.get('emailAddress')})")
        else:
            print("✅ Connection Authenticated!")
    else:
        print("❌ Connection Failed. Check your credentials in .env.")
        return
    print("-" * 65)

    print("📥 Loading and normalizing Jira documents...")
    documents = connector.load_documents()

    if not documents:
        print("⚠️ No documents were found or parsed.")
        return

    print(f"\n📄 Successfully normalized {len(documents)} intermediate Document(s).")
    print("🔄 Building Open Knowledge Format (OKF v0.2) Bundle...\n")

    bundle = OKFBundle(name="Jira Knowledge Bundle", okf_version="0.2")

    for idx, doc in enumerate(documents, 1):
        slug = sanitize_filename(f"{doc.metadata.id}_{doc.metadata.title}")
        rel_path = f"{slug}.okf.md"

        # Project-level overview Documents carry 'project_type' in extra.
        is_project = bool(doc.metadata.extra.get("project_type"))

        concept = OKFConcept.from_intermediate_document(
            doc=doc,
            concept_type="Project" if is_project else "Issue",
            tags=["jira", "issue" if not is_project else "project", "task", "tracking"],
            author="jira_connector/v1.0",
            permissions=OKFPermissions(
                allowed_roles=["employee", "operations"],
                is_public=False,
            ),
        )

        bundle.add_concept(rel_path, concept)

        okf_md_path = BUNDLE_DIR / rel_path
        with open(okf_md_path, "w", encoding="utf-8") as f:
            f.write(concept.to_okf_markdown())

        okf_json_path = BUNDLE_DIR / f"{slug}.okf.json"
        with open(okf_json_path, "w", encoding="utf-8") as f:
            json.dump(concept.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"[{idx}/{len(documents)}] ✅ Generated OKF Concept: \"{doc.metadata.title}\"")
        print(f"    • Trust Tier:     {concept.trust_tier.upper()}")
        print(f"    • Content Hash:   {concept.content_hash[:12]}...")
        print(f"    • Saved File:     {okf_md_path.name}")

    index_path = BUNDLE_DIR / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_index_markdown())
    print(f"\n📑 Generated Bundle Index: {index_path.name}")

    log_path = BUNDLE_DIR / "log.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_log_markdown())
    print(f"🪵 Generated Bundle Log:   {log_path.name}")

    if bundle.concepts:
        first_path, first_concept = next(iter(bundle.concepts.items()))
        print("\n" + "=" * 65)
        print(f"🔍 PREVIEW OF GENERATED OKF v0.2 FILE: {first_path}")
        print("=" * 65)
        full_md = first_concept.to_okf_markdown()
        preview_lines = full_md.splitlines()[:35]
        print("\n".join(preview_lines))
        if len(full_md.splitlines()) > 35:
            print(f"\n... [{len(full_md.splitlines()) - 35} more lines in file] ...")

    print("\n" + "=" * 65)
    print(f"🎉 OKF v0.2 Knowledge Bundle successfully built with {len(documents)} concept(s) in:")
    print(f"   {BUNDLE_DIR}")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OKF v0.2 Knowledge Bundle from Jira")
    parser.add_argument(
        "--projects",
        type=str,
        default="",
        help="Comma-separated project keys to ingest (default '' = all projects)",
    )
    parser.add_argument(
        "--include-projects",
        action="store_true",
        help="Also generate project-level overview Concepts",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=100,
        help="Maximum number of issues to fetch per project (default 100)",
    )
    args = parser.parse_args()
    run_okf_bundle_generator(
        project_keys=args.projects,
        include_projects=args.include_projects,
        max_issues=args.max_issues,
    )


if __name__ == "__main__":
    main()