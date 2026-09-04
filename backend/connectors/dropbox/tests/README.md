# Dropbox Connector - Test Suite & Execution Guide

This directory contains test runners, extractors, and verification scripts for the **Dropbox Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
|:---|:---|:---|
| [`test_run_okf.py`](test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Ingests Dropbox files/folders and builds a complete, standardized Knowledge Bundle with YAML frontmatter, footnote citations, `index.md`, and `log.md`. | `test_data/okf_bundle/`<br>• `<slug>.okf.md`<br>• `<slug>.okf.json`<br>• `index.md`<br>• `log.md` |
| [`test_run_connector.py`](test_run_connector.py) | **Live Connector & Normalization Runner**. Runs `DropboxConnector` and generates intermediate structured JSON and rendered Markdown. | `test_data/output_document_*.json`<br>`test_data/output_document_*.md` |
| [`test_dropbox_auth.py`](test_dropbox_auth.py) | **Official SDK Connectivity Tester**. Verifies authentication with account info and tests root folder discovery. | `test_data/dropbox_root_entries.json` |
| [`get_refresh_token.py`](get_refresh_token.py) | **OAuth 2.0 Refresh Token Generator**. Interactive CLI helper using `DropboxOAuth2FlowNoRedirect` to obtain a permanent `DROPBOX_REFRESH_TOKEN`. | Terminal output (`DROPBOX_REFRESH_TOKEN=...`) |
| [`test_dropbox_fetch.py`](test_dropbox_fetch.py) | **Raw API Extractor**. Pulls raw Dropbox JSON responses (account, folder listing, file metadata) for offline debugging. | `test_data/test_dropbox_account.json`<br>`test_data/test_dropbox_folder.json` |

---

## 🚀 How to Run

Make sure you are in the workspace root directory:
```bash
cd /Users/ompatil/Desktop/Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, `index.md`, and `log.md`.

- **Run on default path (root `/`)**:
  ```bash
  .venv/bin/python backend/connectors/dropbox/tests/test_run_okf.py
  ```
- **Run on a specific folder**:
  ```bash
  .venv/bin/python backend/connectors/dropbox/tests/test_run_okf.py --path "/01-Basic_Files"
  ```
- **Limit how many files are downloaded**:
  ```bash
  .venv/bin/python backend/connectors/dropbox/tests/test_run_okf.py --max-files 50
  ```

---

### 2. Test the Live Dropbox Connector (Intermediate Representation)
Validates connection, lists files/folders, downloads text files, and outputs intermediate Document JSON and Markdown.

- **Run on root folder**:
  ```bash
  .venv/bin/python backend/connectors/dropbox/tests/test_run_connector.py
  ```
- **Run on a specific folder**:
  ```bash
  .venv/bin/python backend/connectors/dropbox/tests/test_run_connector.py --path "/01-Basic_Files"
  ```

---

### 3. Verify Authentication & Connectivity
```bash
.venv/bin/python backend/connectors/dropbox/tests/test_dropbox_auth.py
```

---

### 4. Generate a Permanent Refresh Token
```bash
.venv/bin/python backend/connectors/dropbox/tests/get_refresh_token.py
```

---

## 💾 Where the Data is Stored

All test outputs and generated files are saved inside **`backend/connectors/dropbox/test_data/`** (untracked in Git):

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
├── dropbox_root_entries.json          <-- Live root folder entries from SDK test
├── test_dropbox_account.json          <-- Raw Dropbox account metadata payload
└── test_dropbox_folder.json           <-- Raw Dropbox folder listing payload
```

---

## ⚙️ Prerequisites (.env Configuration)

Ensure your `.env` file contains either:

```env
# Recommended (Permanent OAuth with Auto-Refresh):
DROPBOX_APP_KEY=your_app_key
DROPBOX_APP_SECRET=your_app_secret
DROPBOX_REFRESH_TOKEN=your_refresh_token

# Or Direct Access Token:
DROPBOX_ACCESS_TOKEN=sl.u.your_access_token
```
