"""
Unified Notion Test Data Extractor.

Fetches Notion API test data with options to retrieve:
1. Overall Block / Page Object (/v1/blocks/{PAGE_ID})
2. Underlying Children Blocks (/v1/blocks/{PAGE_ID}/children) with full recursion
   for nested blocks (has_children == True) and database queries (child_database).
3. Both objects simultaneously into separate JSON files in test_data/
"""

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from dotenv import find_dotenv, load_dotenv
import requests

# Load environment variables (.env file)
load_dotenv(find_dotenv())

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_VERSION = "2022-06-28"

BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

# Resolve directory paths dynamically
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = SCRIPT_DIR.parent / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def check_credentials() -> None:
    """Validates that NOTION_TOKEN and NOTION_PAGE_ID are configured."""
    if not NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN is missing. Please set it in your .env file.")
    if not PAGE_ID:
        raise ValueError("NOTION_PAGE_ID is missing. Please set it in your .env file.")


def fetch_overall_block(page_id: str, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Fetches the root/overall block metadata from GET /v1/blocks/{page_id}.
    Saves the JSON result to output_file if specified.
    """
    clean_id = page_id.replace("-", "")
    url = f"{BASE_URL}/blocks/{clean_id}"

    print(f"\n[1/2] Fetching overall block for ID: {clean_id}...")
    response = requests.get(url, headers=HEADERS)
    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    data = response.json()

    out_path = output_file or (TEST_DATA_DIR / "test_notion_block.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"✅ Overall block successfully saved to: {out_path.name}")
    print(f"   Block Type: {data.get('type')}")
    print(f"   Has Children: {data.get('has_children')}")
    return data


def fetch_database_rows(database_id: str) -> List[Dict[str, Any]]:
    """
    Queries all rows/items inside a Notion child_database via POST /v1/databases/{id}/query.
    Handles cursor pagination.
    """
    clean_id = database_id.replace("-", "")
    url = f"{BASE_URL}/databases/{clean_id}/query"
    rows: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        body: Dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor

        response = requests.post(url, headers=HEADERS, json=body)
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After", 1)))
            continue
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])
        rows.extend(results)

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return rows


def fetch_blocks_recursive(
    block_id: str,
    fetch_nested: bool = True,
    fetch_db_rows: bool = True,
    max_depth: int = 4
) -> List[Dict[str, Any]]:
    """
    Fetches all blocks for a given ID, recursively expanding any block where:
    - has_children == True (toggles, callouts, nested lists, sub-pages)
    - type == 'child_database' (queries database rows/todo items)
    """
    clean_id = block_id.replace("-", "")
    url = f"{BASE_URL}/blocks/{clean_id}/children"
    all_blocks: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor

        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After", 1)))
            continue
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        for block in results:
            b_id = block.get("id")
            b_type = block.get("type")
            has_children = block.get("has_children", False)

            # 1. Expand Database rows (e.g. "Todo List" database)
            if fetch_db_rows and b_type == "child_database" and b_id:
                print(f"   ↳ Querying child_database rows for: '{block.get('child_database', {}).get('title', b_id)}'...")
                db_rows = fetch_database_rows(b_id)
                block["database_rows"] = db_rows
                print(f"     Found {len(db_rows)} database items.")

            # 2. Recursively fetch child blocks for blocks with has_children == True
            elif fetch_nested and has_children and max_depth > 0 and b_id:
                print(f"   ↳ Fetching nested children for block {b_id} (type: {b_type})...")
                nested_children = fetch_blocks_recursive(
                    block_id=b_id,
                    fetch_nested=fetch_nested,
                    fetch_db_rows=fetch_db_rows,
                    max_depth=max_depth - 1
                )
                block["children"] = nested_children
                print(f"     Found {len(nested_children)} nested blocks.")
            else:
                block["children"] = []

            all_blocks.append(block)

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return all_blocks


def fetch_underlying_children(
    page_id: str,
    output_file: Optional[Path] = None,
    recursive: bool = True
) -> Dict[str, Any]:
    """
    Fetches all underlying children blocks from GET /v1/blocks/{page_id}/children.
    Recursively inspects blocks where has_children == True or type == 'child_database'.
    Saves the complete results JSON to output_file.
    """
    clean_id = page_id.replace("-", "")

    print(f"\n[2/2] Fetching underlying children for ID: {clean_id} (recursive={recursive})...")
    all_results = fetch_blocks_recursive(clean_id, fetch_nested=recursive, fetch_db_rows=recursive)

    complete_payload = {
        "object": "list",
        "results": all_results,
        "total_root_blocks": len(all_results),
        "has_more": False,
        "next_cursor": None,
    }

    out_path = output_file or (TEST_DATA_DIR / "test_notion_children.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(complete_payload, f, indent=4, ensure_ascii=False)

    print(f"✅ Underlying children ({len(all_results)} root blocks + nested children) saved to: {out_path.name}")
    return complete_payload


def main() -> None:
    """Main CLI entrypoint providing menu options or command line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified Notion test data extractor (Overall Block & Underlying Children)"
    )
    parser.add_argument(
        "--option",
        choices=["block", "children", "both"],
        help="Select extraction mode: 'block' (root block), 'children' (child blocks), or 'both'",
    )
    parser.add_argument(
        "--page-id",
        default=PAGE_ID,
        help="Optional Notion Page/Block ID (defaults to NOTION_PAGE_ID in .env)",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Disable recursive fetching of nested children (has_children == True)",
    )

    args = parser.parse_args()

    check_credentials()
    target_id = args.page_id or PAGE_ID
    recursive = not args.non_recursive

    # If no CLI option provided, prompt interactively
    selected_option = args.option
    if not selected_option:
        print("\n================ Notion Test Data Extractor ================")
        print(f"Target Page ID: {target_id}")
        print("1. Get overall block metadata   -> test_notion_block.json")
        print("2. Get underlying children (all) -> test_notion_children.json")
        print("3. Get both in separate files   -> (test_notion_block.json & test_notion_children.json)")
        print("=============================================================")

        choice = input("Enter choice (1, 2, or 3) [default: 3]: ").strip()
        if choice == "1":
            selected_option = "block"
        elif choice == "2":
            selected_option = "children"
        else:
            selected_option = "both"

    if selected_option in ("block", "both"):
        fetch_overall_block(target_id)

    if selected_option in ("children", "both"):
        fetch_underlying_children(target_id, recursive=recursive)

    print("\n🎉 Extraction complete!\n")


if __name__ == "__main__":
    main()
