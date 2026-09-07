"""
End-to-End OKF v0.2 Knowledge Bundle Generator for Dropbox.

Ingests Dropbox files/folders, converts them into standard OKF v0.2 Concepts,
and builds a complete Knowledge Bundle with:
- <file_slug>.okf.md (YAML Frontmatter + Markdown Body + Footnote Citations)
- <file_slug>.okf.json (Complete JSON metadata & structured records)
- index.md (Bundle directory listing for progressive disclosure)
- log.md (Chronological update history log)
"""

import argparse
import json
import os
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

from backend.connectors.dropbox.connector import DropboxConnector
from backend.models.okf import OKFBundle, OKFConcept, OKFPermissions

SCRIPT_DIR = Path(__file__).resolve().parent
DROPBOX_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = DROPBOX_DIR / "test_data"
BUNDLE_DIR = TEST_DATA_DIR / "okf_bundle"
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Converts a path/title into a clean filename slug."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)[:60] or "dropbox_item"


def run_okf_bundle_generator(path: str = "", max_files: int = 200) -> None:
    print("\n" + "=" * 65)
    print("📦 DROPBOX CONNECTOR - OKF v0.2 KNOWLEDGE BUNDLE GENERATOR")
    print("=" * 65)

    try:
        connector = DropboxConnector(root_path=path, max_files=max_files)
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return

    print("📡 Connecting to Dropbox API...")
    if not connector.test_connection():
        print("❌ Connection Failed. Check your credentials in .env.")
        return

    account = connector.client.get_current_account()
    if account:
        print(f"✅ Connection Authenticated as: {account.get('display_name')} ({account.get('email')})")
    else:
        print("✅ Connection Authenticated!")
    print("-" * 65)

    print("📥 Loading and normalizing Dropbox documents...")
    documents = connector.load_documents()

    if not documents:
        print("⚠️ No documents were found or parsed.")
        return

    print(f"\n📄 Successfully normalized {len(documents)} intermediate Document(s).")
    print("🔄 Building Open Knowledge Format (OKF v0.2) Bundle...\n")

    # Create OKF Bundle
    bundle = OKFBundle(name="Dropbox Knowledge Bundle", okf_version="0.2")

    for idx, doc in enumerate(documents, 1):
        slug = sanitize_filename(doc.metadata.title)
        rel_path = f"{slug}.okf.md"

        is_folder = doc.metadata.extra.get("kind") == "folder"

        # Transform Document to OKF v0.2 Concept
        concept = OKFConcept.from_intermediate_document(
            doc=doc,
            concept_type="Folder" if is_folder else "File",
            tags=["dropbox", "folder" if is_folder else "file", "document"],
            author="dropbox_connector/v1.0",
            permissions=OKFPermissions(
                allowed_roles=["employee", "operations"],
                is_public=False,
            ),
        )

        bundle.add_concept(rel_path, concept)

        # 1. Save individual .okf.md file
        okf_md_path = BUNDLE_DIR / rel_path
        with open(okf_md_path, "w", encoding="utf-8") as f:
            f.write(concept.to_okf_markdown())

        # 2. Save individual .okf.json file
        okf_json_path = BUNDLE_DIR / f"{slug}.okf.json"
        with open(okf_json_path, "w", encoding="utf-8") as f:
            json.dump(concept.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"[{idx}/{len(documents)}] ✅ Generated OKF Concept: \"{doc.metadata.title}\"")
        print(f"    • Trust Tier:     {concept.trust_tier.upper()}")
        print(f"    • Content Hash:   {concept.content_hash[:12]}...")
        print(f"    • Saved File:     {okf_md_path.name}")

    # 3. Generate and Save index.md
    index_path = BUNDLE_DIR / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_index_markdown())
    print(f"\n📑 Generated Bundle Index: {index_path.name}")

    # 4. Generate and Save log.md
    log_path = BUNDLE_DIR / "log.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(bundle.generate_log_markdown())
    print(f"🪵 Generated Bundle Log:   {log_path.name}")

    # Display Preview of First Generated Concept
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
    parser = argparse.ArgumentParser(description="Generate OKF v0.2 Knowledge Bundle from Dropbox")
    parser.add_argument(
        "--path",
        type=str,
        default="",
        help="Dropbox root path to ingest (default '' = whole account)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Max text files to download (default 200)",
    )
    args = parser.parse_args()
    run_okf_bundle_generator(path=args.path, max_files=args.max_files)


if __name__ == "__main__":
    main()
