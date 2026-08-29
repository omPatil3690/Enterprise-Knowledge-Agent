"""
Unified Dropbox Test Data Extractor.

Fetches Dropbox API test data with options to retrieve:
1. Account metadata (GET /2/users/get_current_account)
2. Folder listing (POST /2/files/list_folder, recursive)
3. File metadata (POST /2/files/get_metadata)
4. All objects simultaneously into separate JSON files in test_data/
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

DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")

API_BASE = "https://api.dropboxapi.com/2"
HEADERS = {
    "Authorization": f"Bearer {DROPBOX_TOKEN}",
    "Content-Type": "application/json",
}

# Resolve directory paths dynamically
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def check_credentials() -> None:
    """Validates that DROPBOX_TOKEN is configured."""
    if not DROPBOX_TOKEN:
        raise ValueError(
            "DROPBOX_TOKEN is missing. Please set it in your .env file."
        )


def post(endpoint: str, body: Dict[str, Any]) -> requests.Response:
    """Posts to a Dropbox JSON endpoint with a simple 429 retry."""
    url = f"{API_BASE}/{endpoint}"
    response = requests.post(url, headers=HEADERS, json=body)
    if response.status_code == 429:
        import time
        time.sleep(2)
        response = requests.post(url, headers=HEADERS, json=body)
    return response


def fetch_account_metadata(output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Fetches the authenticated account metadata from /2/users/get_current_account."""
    print("\n[1/3] Fetching current account metadata...")
    response = post("users/get_current_account", {})
    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    data = response.json()

    out_path = output_file or (TEST_DATA_DIR / "test_dropbox_account.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    name = data.get("name", {})
    print(f"✅ Account saved to: {out_path.name}")
    print(f"   Display Name: {name.get('display_name')}")
    print(f"   Email: {data.get('email')}")
    print(f"   Account Type: {data.get('account_type', {}).get('.tag')}")
    return data


def fetch_folder_listing(
    path: str = "",
    recursive: bool = True,
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetches a folder listing from POST /2/files/list_folder (cursor paginated)."""
    print(f"\n[2/3] Fetching folder listing for path: '{path or '/'}' (recursive={recursive})...")
    entries: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        body: Dict[str, Any] = {"path": path or "", "recursive": recursive, "limit": 1000}
        endpoint = "files/list_folder"
        if cursor:
            endpoint = "files/list_folder/continue"
            body = {"cursor": cursor}

        response = post(endpoint, body)
        print(f"Status Code: {response.status_code}")
        response.raise_for_status()

        data = response.json()
        entries.extend(data.get("entries", []))

        if not data.get("has_more"):
            break
        cursor = data.get("cursor")

    payload = {"entries": entries, "total": len(entries)}

    out_path = output_file or (TEST_DATA_DIR / "test_dropbox_folder.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✅ Folder listing saved to: {out_path.name}")
    print(f"   Total entries: {len(entries)}")
    return payload


def fetch_file_metadata(path: str, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Fetches a single file/folder's metadata from POST /2/files/get_metadata."""
    print(f"\n[3/3] Fetching metadata for path: '{path}'...")
    response = post("files/get_metadata", {"path": path})
    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    data = response.json()

    out_path = output_file or (TEST_DATA_DIR / f"test_dropbox_metadata_{path.strip('/').replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Metadata saved to: {out_path.name}")
    print(f"   Name: {data.get('name')}")
    print(f"   Path: {data.get('path_lower')}")
    print(f"   Type: {data.get('.tag')}")
    return data


def main() -> None:
    """Main CLI entrypoint providing menu options or command line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified Dropbox test data extractor (Account, Folder listing, File metadata)"
    )
    parser.add_argument(
        "--option",
        choices=["account", "folder", "metadata", "both"],
        help="Select extraction mode: 'account', 'folder', 'metadata', or 'both'",
    )
    parser.add_argument(
        "--path",
        default="",
        help="Dropbox path to list or get metadata for (default: account root '').",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Disable recursive folder listing",
    )

    args = parser.parse_args()

    check_credentials()
    recursive = not args.non_recursive

    # If no CLI option provided, prompt interactively
    selected_option = args.option
    if not selected_option:
        print("\n================ Dropbox Test Data Extractor ================")
        print(f"Target Path: {args.path or '/'}")
        print("1. Get account metadata  -> test_dropbox_account.json")
        print("2. Get folder listing    -> test_dropbox_folder.json")
        print("3. Get file metadata     -> test_dropbox_metadata_<path>.json")
        print("4. Get all in separate files")
        print("=============================================================")

        choice = input("Enter choice (1, 2, 3, or 4) [default: 4]: ").strip()
        if choice == "1":
            selected_option = "account"
        elif choice == "2":
            selected_option = "folder"
        elif choice == "3":
            selected_option = "metadata"
        else:
            selected_option = "both"

    if selected_option in ("account", "both"):
        fetch_account_metadata()

    if selected_option in ("folder", "both"):
        fetch_folder_listing(path=args.path, recursive=recursive)

    if selected_option in ("metadata", "both"):
        target = args.path or "/"
        fetch_file_metadata(target)

    print("\n🎉 Extraction complete!\n")


if __name__ == "__main__":
    main()
