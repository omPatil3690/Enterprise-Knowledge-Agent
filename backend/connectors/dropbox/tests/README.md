# Dropbox Connector - Test Suite & Execution Guide

This directory contains test runners, extractors, and verification scripts for the **Dropbox Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
|:---|:---|:---|
| [`test_run_okf.py`](test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Ingests Dropbox files/folders and builds a complete, standardized Knowledge Bundle. | `test_data/okf_bundle/` (`.okf.md`, `.okf.json`, `index.md`, `log.md`) |
| [`test_run_connector.py`](test_run_connector.py) | **Live Connector & Normalization Runner**. Runs `DropboxConnector` and generates intermediate structured JSON and rendered Markdown. | `test_data/output_document_*.json`<br>`test_data/output_document_*.md` |
| [`test_dropbox_fetch.py`](test_dropbox_fetch.py) | **Raw API Extractor**. Pulls raw Dropbox JSON responses (account, folder listing, file metadata). | `test_data/test_dropbox_account.json`<br>`test_data/test_dropbox_folder.json`<br>`test_data/test_dropbox_metadata_*.json` |
| [`test_dropbox_extraction.py`](test_dropbox_extraction.py) | Entry point forwarding directly to `test_dropbox_fetch.py`. | Same as `test_dropbox_fetch.py` |

---

## 🚀 How to Run

Make sure you are in the workspace root directory:
```bash
cd Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, `index.md`, and `log.md`.

- **Run on default path (root `/`)**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_okf.py
  ```
- **Run on a specific folder**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_okf.py --path "/MyNotes"
  ```
- **Skip folders (walk files only)**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_okf.py --no-folders
  ```

---

### 2. Test the Live Dropbox Connector (Intermediate Representation)
Validates connection, lists files/folders, downloads text files, and outputs intermediate Document JSON and Markdown.

- **Run on default path (root `/`)**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_connector.py
  ```
- **Run on a specific folder**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_connector.py --path "/MyNotes"
  ```
- **Skip folders (walk files only)**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_connector.py --no-folders
  ```
- **Limit how many files are downloaded**:
  ```bash
  python backend/connectors/dropbox/tests/test_run_connector.py --max-files 50
  ```

---

### 3. Fetch Raw Dropbox API Payloads (Debugging / Offline Testing)
Fetches raw Dropbox API responses to inspect low-level structures or save test fixtures.

- **Interactive Menu Mode**:
  ```bash
  python backend/connectors/dropbox/tests/test_dropbox_fetch.py
  ```
- **Fetch account metadata only**:
  ```bash
  python backend/connectors/dropbox/tests/test_dropbox_fetch.py --option account
  ```
- **Fetch folder listing only**:
  ```bash
  python backend/connectors/dropbox/tests/test_dropbox_fetch.py --option folder --path "/MyNotes"
  ```
- **Fetch file metadata only**:
  ```bash
  python backend/connectors/dropbox/tests/test_dropbox_fetch.py --option metadata --path "/MyNotes/notes.md"
  ```
- **Fetch all at once**:
  ```bash
  python backend/connectors/dropbox/tests/test_dropbox_fetch.py --option both
  ```

> `test_dropbox_extraction.py` is an alias for `test_dropbox_fetch.py`; run it the same way.

---

## 💾 Where the Data is Stored

All test outputs and generated files are saved inside **`backend/connectors/dropbox/test_data/`**:

```
backend/connectors/dropbox/test_data/
│
├── okf_bundle/                        <-- OKF v0.2 Knowledge Bundle
│   ├── index.md                       <-- Directory listing for Progressive Disclosure (§8)
│   ├── log.md                         <-- Chronological update history (§9)
│   ├── <slug>.okf.md                  <-- Concept document (YAML Frontmatter + Markdown Body)
│   └── <slug>.okf.json                <-- Machine-readable JSON schema (for Vector DB / Neo4j)
│
├── output_document_*.json             <-- Intermediate structured Document JSON per file/folder
├── output_document_*.md               <-- Rendered Markdown document preview per file/folder
│
├── test_dropbox_account.json          <-- Raw Dropbox account metadata payload
├── test_dropbox_folder.json           <-- Raw Dropbox folder listing payload
└── test_dropbox_metadata_*.json       <-- Raw Dropbox file/folder metadata payload
```

---

## ⚙️ Prerequisites (.env Configuration)

Ensure your `.env` file at the root of the project contains:

```env
DROPBOX_TOKEN="sl.your_access_token_here"
```

Generate an access token at:
https://www.dropbox.com/developers/apps

1. **Create app** → *Dropbox API* → scope for a personal retrieval system: `account_info.read`, `files.metadata.read`, `files.content.read` (or *Full Dropbox*).
2. Under **Settings** → **OAuth 2 / Generated access token** → **Generate**.

The connector uses the Dropbox HTTP API via `requests` (no separate `dropbox` SDK required).
