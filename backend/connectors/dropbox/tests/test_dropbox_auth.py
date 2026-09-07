"""
Dropbox Connectivity and Authentication Test.

Uses the official Dropbox Python SDK (dropbox.Dropbox) to authenticate,
retrieve user account info (users_get_current_account), and inspect root files.
"""

import json
import os
from pathlib import Path
import sys
import dotenv

# Ensure project root is in sys.path
SCRIPT_PATH = Path(__file__).resolve()
current = SCRIPT_PATH.parent
while current != current.parent:
    if (current / "backend").exists():
        if str(current) not in sys.path:
            sys.path.insert(0, str(current))
        break
    current = current.parent

import dropbox
from dropbox.exceptions import AuthError

dotenv.load_dotenv(current / ".env")

SCRIPT_DIR = Path(__file__).resolve().parent
DROPBOX_DIR = SCRIPT_DIR.parent
TEST_DATA_DIR = DROPBOX_DIR / "test_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def test_auth():
    print("=" * 65)
    print("📦 DROPBOX SDK - AUTHENTICATION & CONNECTIVITY TEST")
    print("=" * 65)

    access_token = os.getenv("DROPBOX_ACCESS_TOKEN") or os.getenv("DROPBOX_TOKEN")
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")

    if not access_token and not (app_key and app_secret and refresh_token):
        print("❌ Error: No Dropbox credentials found in .env.")
        print("Please configure DROPBOX_ACCESS_TOKEN (or DROPBOX_APP_KEY + DROPBOX_APP_SECRET + DROPBOX_REFRESH_TOKEN).")
        return

    # Initialize official SDK
    if app_key and app_secret and refresh_token:
        print("🔑 Initializing Dropbox client with App Key/Secret & Refresh Token...")
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token,
        )
    else:
        print("🔑 Initializing Dropbox client with Access Token...")
        dbx = dropbox.Dropbox(access_token)

    try:
        # 1. Verify Account
        print("📡 Calling dbx.users_get_current_account()...")
        account = dbx.users_get_current_account()
        print("✅ Successfully connected to Dropbox!")
        print(f"    • Display Name: {account.name.display_name}")
        print(f"    • Email:        {account.email}")
        print(f"    • Account ID:   {account.account_id}")
        print(f"    • Country:      {account.country}")
        print("-" * 65)

        # 2. Test Listing Root Folder
        print("📂 Testing dbx.files_list_folder('') at root namespace...")
        result = dbx.files_list_folder(path="", limit=20)
        print(f"✅ Found {len(result.entries)} item(s) at root:")

        entries_summary = []
        for entry in result.entries:
            tag = type(entry).__name__.replace("Metadata", "").lower()
            print(f"    • [{tag.upper()}] {entry.name} ({entry.path_display})")
            entries_summary.append({
                "name": entry.name,
                "path_display": entry.path_display,
                "path_lower": entry.path_lower,
                "type": tag,
                "id": getattr(entry, "id", None),
                "size": getattr(entry, "size", None),
            })

        # Save metadata fixture silently for inspection
        out_file = TEST_DATA_DIR / "dropbox_root_entries.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(entries_summary, f, indent=2, ensure_ascii=False)

        print(f"\n🎉 Test metadata saved to: {out_file.relative_to(current)}")
        print("=" * 65 + "\n")

    except AuthError as e:
        print(f"❌ Dropbox Authentication Error: {e}")
    except Exception as e:
        print(f"❌ Connection error: {e}")


if __name__ == "__main__":
    test_auth()
