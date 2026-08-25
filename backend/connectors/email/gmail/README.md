# Gmail Connector Setup & OAuth 2.0 Guide

This guide details the end-to-end setup for the **Gmail Enterprise Connector** using the official Google Gmail API with OAuth 2.0 authentication and the principle of least privilege (`gmail.readonly`).

---

## 🏗️ Architecture & Authentication Model

Gmail user data is private and sensitive. Rather than using static API keys or broad account access, this connector uses:
- **OAuth 2.0 Desktop Application Flow**: User grants consent via browser.
- **Least Privilege Scope (`https://www.googleapis.com/auth/gmail.readonly`)**: Allows reading emails and metadata without permission to send, modify, or delete emails.
- **`credentials.json`**: Identifies your client application to Google Cloud.
- **`token.json`**: Secure local token storing the user's refresh and access tokens (generated automatically on first login).

```
                      ┌──────────────────────┐
                      │ Google Cloud Console │
                      └──────────┬───────────┘
                                 │
                   Downloads credentials.json (OAuth Client)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ test_gmail.py / Agent │
                     └───────────┬───────────┘
                                 │
                 1. Opens Google OAuth Browser Flow
                 2. User Signs In & Grants Permission
                 3. Saves token.json locally
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │ Gmail REST API v1   │
                      │  • messages.list()  │
                      │  • messages.get()   │
                      └─────────────────────┘
```

---

## 📋 Step-by-Step Setup Guide

### Step 1 — Create a Google Cloud Project
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Sign in with the Google account you will use for development.
3. In the top project selector dropdown, click **New Project**.
4. Name the project (e.g., `Enterprise Knowledge Agent`).
5. Click **Create** and ensure the project is selected.

---

### Step 2 — Enable the Gmail API
1. In Google Cloud Console, open the sidebar menu: `☰` $\rightarrow$ **APIs & Services** $\rightarrow$ **Library** (or visit [API Library](https://console.cloud.google.com/apis/library)).
2. Search for `Gmail API`.
3. Select **Gmail API — Google Workspace** and click **Enable**.

---

### Step 3 — Configure OAuth Consent Screen
1. Go to `☰` $\rightarrow$ **Google Auth Platform** (or **APIs & Services** $\rightarrow$ **OAuth consent screen**).
2. If prompted, click **Get Started**.

---

### Step 4 — Configure Branding
1. **App name**: `Enterprise Knowledge Agent`
2. **User support email**: Your Gmail address.
3. **Developer contact information**: Your Gmail address.
4. Click **Save and Continue**.

---

### Step 5 — Configure Audience
1. Go to **Google Auth Platform** $\rightarrow$ **Audience**.
2. Select **External** (standard for testing with individual Google accounts).
3. Click **Save and Continue**.

---

### Step 6 — Add Test Users
> [!IMPORTANT]
> Because the app is in "Testing" mode, only explicitly added test users can authorize the application.

1. In the **Audience** section, locate **Test users**.
2. Click **+ Add users**.
3. Enter the Gmail address(es) you will use for testing.
4. Click **Save**.

---

### Step 7 — Configure the Gmail Scope
1. Go to **Google Auth Platform** $\rightarrow$ **Data Access** (or **Scopes**).
2. Click **Add or Remove Scopes**.
3. Add the read-only scope:
   ```
   https://www.googleapis.com/auth/gmail.readonly
   ```
4. Click **Update** and **Save**.

> [!CAUTION]
> Do **NOT** use `https://mail.google.com/` as it grants full control to send, modify, and delete mail. Always use the least-privilege `gmail.readonly` scope.

---

### Step 8 — Create Desktop OAuth Client
1. Go to **Google Auth Platform** $\rightarrow$ **Clients** (or **APIs & Services** $\rightarrow$ **Credentials**).
2. Click **Create Client** (or **Create Credentials** $\rightarrow$ **OAuth client ID**).
3. Select **Application type**: `Desktop app`.
4. Name it `Enterprise Knowledge Agent - Gmail`.
5. Click **Create**.

---

### Step 9 — Download `credentials.json`
1. After client creation, click the download icon (⬇️) to download the client JSON file.
2. It will be named something like `client_secret_xxxxxxxxxx.json`.
3. Rename this file to:
   ```
   credentials.json
   ```
4. Place it inside the `backend/connectors/email/` directory (or workspace root).

> [!WARNING]
> Never commit `credentials.json` or `token.json` to Git! Both are automatically ignored by [`.gitignore`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/.gitignore).

---

### Step 10 — Install Dependencies

Ensure your virtual environment is active, then install the required Google client libraries:

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

### Step 11 — Run Authentication & First Test

Execute the test runner:

```bash
python backend/connectors/email/gmail/tests/test_gmail.py
```

1. A local browser tab will open asking you to sign in to Google.
2. Sign in with the account you added to **Test users**.
3. Click **Continue** when prompted with the consent screen.
4. Once authorized, `token.json` is generated locally for all future headless/automated requests.
5. The script will fetch and display the last 5 messages from your inbox.

---

## 📂 File Layout

```
backend/connectors/email/
├── credentials.json        # OAuth Client Secret (Ignored by Git)
└── gmail/
    ├── README.md           # This setup guide
    ├── client.py           # Gmail API wrapper & OAuth token manager (Upcoming)
    ├── parser.py           # MIME / RFC 2822 email parser (Upcoming)
    ├── connector.py        # BaseConnector implementation (Upcoming)
    └── tests/
        ├── test_gmail.py   # Quickstart validation script
        └── token.json      # Stored user token (Ignored by Git)
```

---

## 🔄 Ingestion Flow (Roadmap)

1. **Discovery (`messages.list`)**: Fetches message/thread IDs with query filters (e.g., `after:2026/01/01`, `label:INBOX`).
2. **Payload Retrieval (`messages.get`)**: Pulls full MIME payloads (`format='full'`).
3. **MIME Parser (`parser.py`)**:
   - Headers: `From`, `To`, `Cc`, `Subject`, `Date`, `Message-ID`.
   - Body: Extracts `text/plain` or cleans `text/html`.
   - Threads: Groups emails into conversations.
4. **OKF Normalization**: Emits typed `OKFConcept` documents with provenance citations to `gmail://messages/{id}`.
