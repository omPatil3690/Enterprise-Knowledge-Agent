"""
End-to-End OKF v0.2 Bundle Generator and Tester for Notion.

Ingests Notion pages, converts them into standard OKF v0.2 Concepts,
and builds a complete Knowledge Bundle with:
- <concept_name>.okf.md (YAML Frontmatter + Markdown Body + Footnote Citations)
- <concept_name>.okf.json (Complete JSON metadata & structured records)
- index.md (Bundle directory listing for progressive disclosure)
- log.md (Chronological update history log)
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from dotenv import find_dotenv, load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(find_dotenv())

from backend.connectors.notion.connector import NotionConnector
from backend.models.okf import OKFBundle, OKFConcept, OKFPermissions

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
BUNDLE_DIR = TEST_DATA_DIR / "okf_bundle"
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Converts a title into a clean filename slug."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean) or "concept"


def run_okf_test(page_id: str = None, auto_discover: bool = False) -> None:
    token = os.getenv("NOTION_TOKEN")
    target_page_id = page_id or os.getenv("NOTION_PAGE_ID")

    print("\n" + "=" * 65)
    print("📦 ENTERPRISE KNOWLEDGE AGENT - OKF v0.2 BUNDLE GENERATOR")
    print("=" * 65)

    if not token:
        print("❌ ERROR: NOTION_TOKEN is missing in your .env file.")
        return

    connector = NotionConnector(token=token, default_page_id=target_page_id)

    print("📡 Connecting to Notion API...")
    if not connector.test_connection():
        print("❌ Connection Failed. Check your NOTION_TOKEN in .env.")
        return
    print("✅ Connection Authenticated!")
    print("-" * 65)

    # Ingest intermediate documents
    documents = []
    if auto_discover:
        print("🌐 Ingesting all accessible pages in workspace...")
        documents = connector.load_documents(auto_discover=True)
    elif target_page_id:
        print(f"📥 Ingesting Notion page: {target_page_id}...")
        doc = connector.load_document_by_id(target_page_id)
        if doc:
            documents.append(doc)
    else:
        print("❌ Please provide a --page-id or set NOTION_PAGE_ID in .env.")
        return

    if not documents:
        print("⚠️ No documents were found or parsed.")
        return

    print(f"📄 Ingested {len(documents)} intermediate document(s).")
    print("🔄 Converting into Open Knowledge Format (OKF v0.2) Concepts...\n")

    # Create OKF Bundle
    bundle = OKFBundle(name="Enterprise Knowledge Bundle", okf_version="0.2")

    for idx, doc in enumerate(documents, 1):
        slug = sanitize_filename(doc.metadata.title or f"notion_page_{doc.metadata.id[:8]}")
        rel_path = f"{slug}.okf.md"

        # Transform to OKF v0.2 Concept
        concept = OKFConcept.from_intermediate_document(
            doc=doc,
            concept_type="Notion Page",
            tags=["notion", "enterprise-knowledge"],
            author="notion_connector/v1.0",
            permissions=OKFPermissions(
                allowed_roles=["engineering", "product", "employee"],
                is_public=False
            ),
        )

        bundle.add_concept(rel_path, concept)

        # Save individual .okf.md file
        okf_md_path = BUNDLE_DIR / rel_path
        with open(okf_md_path, "w", encoding="utf-8") as f:
            f.write(concept.to_okf_markdown())

        # Save individual .okf.json file
        okf_json_path = BUNDLE_DIR / f"{slug}.okf.json"
        with open(okf_json_path, "w", encoding="utf-8") as f:
            json.dump(concept.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"[{idx}/{len(documents)}] ✅ Generated OKF Concept: {doc.metadata.title}")
        print(f"    • Trust Tier:     {concept.trust_tier.upper()}")
        print(f"    • Is Stale:       {concept.is_stale}")
        print(f"    • Content Hash:   {concept.content_hash[:12]}...")
        print(f"    • Saved File:     {okf_md_path.relative_to(PROJECT_ROOT)}")

    # Generate and Save index.md
    index_path = BUNDLE_DIR / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_index_markdown())
    print(f"\n📑 Generated Bundle Index: {index_path.relative_to(PROJECT_ROOT)}")

    # Generate and Save log.md
    log_path = BUNDLE_DIR / "log.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_log_markdown())
    print(f"🪵 Generated Bundle Log:   {log_path.relative_to(PROJECT_ROOT)}")

    # Display Preview of the First Concept
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
    print("🎉 OKF v0.2 Knowledge Bundle successfully built in:")
    print(f"   {BUNDLE_DIR}")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test OKF v0.2 generation from Notion")
    parser.add_argument("--page-id", type=str, default=None, help="Notion Page ID")
    parser.add_argument("--all", action="store_true", help="Auto-discover all workspace pages")
    args = parser.parse_args()
    run_okf_test(page_id=args.page_id, auto_discover=args.all)


if __name__ == "__main__":
    main()
