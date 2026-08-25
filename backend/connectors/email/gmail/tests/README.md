# Gmail Connector - Test Suite & Execution Guide

This directory contains test runners, MIME validators, payload extractors, and verification scripts for the **Gmail Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
| :--- | :--- | :--- |
| [`test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Connects live to Gmail, ingests emails, and builds a complete, standardized Knowledge Bundle with YAML frontmatter, footnote citations, `index.md`, and `log.md`. | `test_data/okf_bundle/`<br>• `<email_slug>.okf.md`<br>• `<email_slug>.okf.json`<br>• `index.md`<br>• `log.md` |
| [`test_run_connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_run_connector.py) | **Live Connector & BaseConnector Lifecycle Runner**. Tests `GmailConnector` against the `BaseConnector` interface (`test_connection`, `load_documents`, `sync_incremental`), generating normalized `Document` JSON and rendered Markdown. | `test_data/output_email_documents.json`<br>`test_data/output_sample_email.md` |
| [`test_parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_parser.py) | **Offline MIME & Payload Parser Validator**. Tests recursive MIME parsing (`multipart/alternative`, `multipart/mixed`), base64 decoding, header normalization, and attachment detection on saved JSON fixtures in `test_data/` without network I/O. | `test_data/parsed_email_documents.json` |
| [`test_gmail.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_gmail.py) | **OAuth 2.0 Quickstart & Raw Payload Downloader**. Runs initial browser OAuth flow, queries inbox, and saves raw Gmail API payloads silently to disk. | `test_data/all_sample_messages.json`<br>`test_data/inbox_messages_list.json`<br>`test_data/message_{id}.json` |

---

## 🚀 How to Run

Make sure you are in the workspace root directory and your virtual environment is active:

```bash
cd /Users/ompatil/Desktop/Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, progressive disclosure `index.md`, and update history `log.md`.

- **Ingest default inbox emails (up to 5)**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_run_okf.py
  ```
- **Ingest with custom search query (e.g. specific sender or label)**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_run_okf.py --query "from:notifications@github.com" --limit 10
  ```
- **Ingest unread emails only**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_run_okf.py --query "is:unread" --limit 15
  ```

---

### 2. Test the Live Gmail Connector (`BaseConnector` Interface)
Validates OAuth authentication, tests reachability, ingests emails, and outputs intermediate structured `Document` JSON and rendered Markdown.

- **Run standard connector ingestion**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_run_connector.py
  ```

---

### 3. Validate Recursive MIME Parsing (Offline / Without Network)
Parses complex multi-part email bodies and attachments from saved test fixtures without making network requests.

- **Run offline parser validation**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_parser.py
  ```

---

### 4. Fetch Raw Gmail API Payloads (Debugging / Fixture Generation)
Performs OAuth consent and downloads raw Gmail API message dictionaries for offline inspection and testing.

- **Download sample message payloads**:
  ```bash
  .venv/bin/python backend/connectors/email/gmail/tests/test_gmail.py
  ```

---

## 💾 Where the Data is Stored

All test outputs, raw JSON payloads, and generated knowledge bundles are saved inside **`backend/connectors/email/gmail/test_data/`** (automatically ignored by Git):

```
backend/connectors/email/gmail/test_data/
│
├── okf_bundle/                        <-- OKF v0.2 Knowledge Bundle
│   ├── index.md                       <-- Directory listing for Progressive Disclosure (§8)
│   ├── log.md                         <-- Chronological update history (§9)
│   ├── <email_slug>.okf.md            <-- Concept document (YAML Frontmatter + Markdown Body)
│   └── <email_slug>.okf.json          <-- Machine-readable JSON schema (for Vector DB / Neo4j)
│
├── output_email_documents.json        <-- Intermediate structured Document JSON
├── output_sample_email.md             <-- Rendered Markdown document preview
│
├── parsed_email_documents.json        <-- Normalized EmailDocument list JSON
├── all_sample_messages.json           <-- Full batch of raw Gmail API message payloads
├── inbox_messages_list.json           <-- Raw message list response
└── message_<id>.json                  <-- Individual raw message payload fixtures
```

---

## ⚙️ Prerequisites & Credentials

1. **OAuth Client Credentials (`credentials.json`)**:
   - Placed in `backend/connectors/email/gmail/credentials.json` or project root.
   - Generated from Google Cloud Console with the `https://www.googleapis.com/auth/gmail.readonly` scope.
2. **Authorized User Token (`token.json`)**:
   - Automatically created upon completing the one-time browser consent prompt.
   - Refresh tokens are automatically handled for headless execution.
