"""
End-to-End OKF v0.2 Knowledge Bundle Generator for GitHub.

Ingests GitHub repositories and issues, converts them into standard OKF v0.2 Concepts,
and builds a complete Knowledge Bundle with:
- <repo_slug>.okf.md (YAML Frontmatter + Markdown Body + Footnote Citations)
- <repo_slug>.okf.json (Complete JSON metadata & structured records)
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
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(find_dotenv())

from backend.connectors.github.connector import GitHubConnector
from backend.models.okf import OKFBundle, OKFConcept, OKFPermissions

SCRIPT_DIR = Path(__file__).resolve().parent
GITHUB_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = GITHUB_DIR / "test_data"
BUNDLE_DIR = TEST_DATA_DIR / "okf_bundle"
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Converts a repo name / title into a clean filename slug."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)[:60] or "repository"


def run_okf_bundle_generator(repos: list = None, auto_discover: bool = True, no_readme: bool = False, no_issues: bool = False) -> None:
    token = os.getenv("GITHUB_TOKEN")

    print("\n" + "=" * 65)
    print("📦 GITHUB CONNECTOR - OKF v0.2 KNOWLEDGE BUNDLE GENERATOR")
    print("=" * 65)

    if not token:
        print("❌ ERROR: GITHUB_TOKEN is missing in your .env file.")
        return

    connector = GitHubConnector(
        token=token,
        include_repos=repos,
        fetch_readme=not no_readme,
        fetch_issues=not no_issues,
    )

    print("📡 Connecting to GitHub API...")
    if not connector.test_connection():
        print("❌ Connection Failed. Check your GITHUB_TOKEN in .env.")
        return

    user = connector.client.get_current_user()
    if user:
        print(f"✅ Connection Authenticated as: {user.get('login')}")
    else:
        print("✅ Connection Authenticated!")
    print("-" * 65)

    print("📥 Loading and normalizing repositories...")
    documents = connector.load_documents(include_repos=repos or None)

    if not documents:
        print("⚠️ No documents were found or parsed.")
        return

    print(f"\n📄 Successfully normalized {len(documents)} intermediate Document(s).")
    print("🔄 Building Open Knowledge Format (OKF v0.2) Bundle...\n")

    # Create OKF Bundle
    bundle = OKFBundle(name="GitHub Knowledge Bundle", okf_version="0.2")

    for idx, doc in enumerate(documents, 1):
        slug = sanitize_filename(doc.metadata.title)
        rel_path = f"{slug}.okf.md"

        # Transform Document to OKF v0.2 Concept
        concept = OKFConcept.from_intermediate_document(
            doc=doc,
            concept_type="Repository",
            tags=["github", "code", "repository"],
            author="github_connector/v1.0",
            permissions=OKFPermissions(
                allowed_roles=["engineering", "product", "employee"],
                is_public=not doc.metadata.extra.get("private", False),
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
        print(f"    • Is Stale:       {concept.is_stale}")
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
    parser = argparse.ArgumentParser(description="Generate OKF v0.2 Knowledge Bundle from GitHub")
    parser.add_argument(
        "--repo",
        action="append",
        default=None,
        help="Explicit 'owner/repo' to ingest. Repeat for multiple. "
             "Defaults to auto-discovery of all repos if omitted.",
    )
    parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip README fetching",
    )
    parser.add_argument(
        "--no-issues",
        action="store_true",
        help="Skip issues/PR fetching",
    )
    args = parser.parse_args()
    run_okf_bundle_generator(
        repos=args.repo,
        auto_discover=not args.repo,
        no_readme=args.no_readme,
        no_issues=args.no_issues,
    )


if __name__ == "__main__":
    main()
