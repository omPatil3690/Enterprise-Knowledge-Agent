"""
Unified GitHub Test Data Extractor.

Fetches GitHub API test data with options to retrieve:
1. Repository metadata (GET /repos/{owner}/{repo})
2. File tree (GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1)
3. Open issues / pull requests (GET /repos/{owner}/{repo}/issues)
4. All three objects simultaneously into separate JSON files in test_data/
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import find_dotenv, load_dotenv
import requests

# Load environment variables (.env file)
load_dotenv(find_dotenv())

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Resolve directory paths dynamically
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def check_credentials() -> None:
    """Validates that GITHUB_TOKEN is configured."""
    if not GITHUB_TOKEN or GITHUB_TOKEN.startswith("ghp_your"):
        raise ValueError(
            "GITHUB_TOKEN is missing or unset. Please set it in your .env file."
        )


def parse_full_name(full_name: str) -> tuple:
    """Splits 'owner/repo' into (owner, repo)."""
    owner, _, repo = full_name.partition("/")
    if not owner or not repo:
        raise ValueError(f"Invalid full name '{full_name}'. Expected 'owner/repo'.")
    return owner, repo


def fetch_repo_metadata(full_name: str, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Fetches repository metadata from GET /repos/{owner}/{repo}."""
    owner, repo = parse_full_name(full_name)
    url = f"{BASE_URL}/repos/{owner}/{repo}"

    print(f"\n[1/3] Fetching repo metadata for: {full_name}...")
    response = requests.get(url, headers=HEADERS)
    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    data = response.json()

    out_path = output_file or (TEST_DATA_DIR / f"test_github_repo_{full_name.replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Repo metadata saved to: {out_path.name}")
    print(f"   Full Name:  {data.get('full_name')}")
    print(f"   Default Branch: {data.get('default_branch')}")
    print(f"   Language:   {data.get('language')}")
    return data


def fetch_file_tree(
    full_name: str,
    branch: str = "HEAD",
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetches the full git file tree of a repository (recursive)."""
    owner, repo = parse_full_name(full_name)
    url = f"{BASE_URL}/repos/{owner}/{repo}/git/trees/{branch}"

    print(f"\n[2/3] Fetching file tree for: {full_name} (branch={branch}, recursive)...")
    response = requests.get(url, headers=HEADERS, params={"recursive": "1"})
    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    data = response.json()

    out_path = output_file or (TEST_DATA_DIR / f"test_github_tree_{full_name.replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ File tree saved to: {out_path.name}")
    print(f"   Truncated: {data.get('truncated')}")
    print(f"   Total tree entries: {len(data.get('tree', []))}")
    return data


def fetch_issues(
    full_name: str,
    state: str = "open",
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetches issues and pull requests for a repository (Link-header paginated)."""
    owner, repo = parse_full_name(full_name)
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues"

    print(f"\n[3/3] Fetching {state} issues/PRs for: {full_name}...")
    results: List[Dict[str, Any]] = []
    current = url
    params: Dict[str, Any] = {"state": state, "per_page": 100}

    while current:
        response = requests.get(current, headers=HEADERS, params=params)
        print(f"Status Code: {response.status_code}")
        response.raise_for_status()

        data = response.json()
        results.extend(data)
        params = {}

        link = response.headers.get("Link", "")
        current = None
        for part in link.split(","):
            ref, _, rel = part.partition(";")
            if "rel=\"next\"" in rel or "rel='next'" in rel:
                current = ref.strip().strip("<>")
                break

    payload = {"object": "list", "results": results, "total": len(results)}

    out_path = output_file or (TEST_DATA_DIR / f"test_github_issues_{full_name.replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✅ Issues saved to: {out_path.name}")
    print(f"   Total issues/PRs: {len(results)}")
    return payload


def main() -> None:
    """Main CLI entrypoint providing menu options or command line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified GitHub test data extractor (Repo metadata, File tree, Issues)"
    )
    parser.add_argument(
        "--option",
        choices=["repo", "tree", "issues", "both"],
        help="Select extraction mode: 'repo', 'tree', 'issues', or 'both'",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="'owner/repo' to extract (e.g. 'Aditya25-yadav/2048'). Defaults to the first repo "
             "discovered from the token if omitted.",
    )
    parser.add_argument(
        "--branch",
        default="HEAD",
        help="Branch or ref for the file tree (default 'HEAD')",
    )
    parser.add_argument(
        "--state",
        default="open",
        choices=["open", "closed", "all"],
        help="Issue state to fetch (default 'open')",
    )

    args = parser.parse_args()

    check_credentials()

    target = args.repo
    if not target:
        print("No --repo provided. Auto-discovering first accessible repo...")
        resp = requests.get(f"{BASE_URL}/user/repos?per_page=1", headers=HEADERS)
        resp.raise_for_status()
        repos = resp.json()
        if not repos:
            raise ValueError("No accessible repositories found for this token.")
        target = repos[0]["full_name"]
        print(f"Auto-selected repo: {target}")

    # If no CLI option provided, prompt interactively
    selected_option = args.option
    if not selected_option:
        print("\n================ GitHub Test Data Extractor ================")
        print(f"Target Repo: {target}")
        print("1. Get repo metadata        -> test_github_repo_<repo>.json")
        print("2. Get file tree            -> test_github_tree_<repo>.json")
        print("3. Get issues / PRs         -> test_github_issues_<repo>.json")
        print("4. Get all in separate files")
        print("=============================================================")

        choice = input("Enter choice (1, 2, 3, or 4) [default: 4]: ").strip()
        if choice == "1":
            selected_option = "repo"
        elif choice == "2":
            selected_option = "tree"
        elif choice == "3":
            selected_option = "issues"
        else:
            selected_option = "both"

    if selected_option in ("repo", "both"):
        fetch_repo_metadata(target)

    if selected_option in ("tree", "both"):
        fetch_file_tree(target, branch=args.branch)

    if selected_option in ("issues", "both"):
        fetch_issues(target, state=args.state)

    print("\n🎉 Extraction complete!\n")


if __name__ == "__main__":
    main()
