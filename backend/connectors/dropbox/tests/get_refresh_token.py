"""
Interactive OAuth Helper to obtain a Dropbox Refresh Token.

Uses DropboxOAuth2FlowNoRedirect with token_access_type='offline'
to generate a permanent DROPBOX_REFRESH_TOKEN.
"""

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
from dropbox import DropboxOAuth2FlowNoRedirect

dotenv.load_dotenv(current / ".env")


def main():
    print("=" * 65)
    print("🔑 DROPBOX OAUTH 2.0 - REFRESH TOKEN GENERATOR")
    print("=" * 65)

    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")

    if not app_key or not app_secret:
        print("❌ Error: DROPBOX_APP_KEY or DROPBOX_APP_SECRET missing in .env")
        print("Please ensure your .env contains:")
        print("DROPBOX_APP_KEY=your_app_key")
        print("DROPBOX_APP_SECRET=your_app_secret")
        return

    # Initialize OAuth flow with offline token access (refresh token)
    auth_flow = DropboxOAuth2FlowNoRedirect(
        consumer_key=app_key,
        consumer_secret=app_secret,
        token_access_type="offline",
        scope=["files.metadata.read", "files.content.read", "account_info.read"],
    )

    authorize_url = auth_flow.start()

    print("\n👉 STEP 1: Open this URL in your browser:\n")
    print(f"   {authorize_url}\n")
    print("👉 STEP 2: Click 'Allow' (sign in if prompted).")
    print("👉 STEP 3: Copy the authorization code shown on screen.\n")

    try:
        auth_code = input("Enter the authorization code here: ").strip()
        if not auth_code:
            print("❌ No authorization code provided.")
            return

        oauth_result = auth_flow.finish(auth_code)

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! OAuth Tokens Generated:")
        print("=" * 65)
        print(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}")
        print(f"DROPBOX_ACCESS_TOKEN={oauth_result.access_token}")
        print("=" * 65)
        print("\n👉 Add this line to your .env file:")
        print(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}\n")

    except Exception as e:
        print(f"❌ Failed to exchange code: {e}")


if __name__ == "__main__":
    main()
