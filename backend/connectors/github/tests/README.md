# GitHub Connector - Test Suite & Execution Guide

This directory contains test runners, extractors, and verification scripts for the **GitHub Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
|:---|:---|:---|
| [`test_run_okf.py`](test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Ingests GitHub repositories and builds a complete, standardized Knowledge Bundle. | `test_data/okf_bundle/` (`.okf.md`, `.okf.json`, `index.md`, `log.md`) |
| [`test_run_connector.py`](test_run_connector.py) | **Live Connector & Normalization Runner**. Runs `GitHubConnector` and generates intermediate structured JSON and rendered Markdown. | `test_data/output_document_<repo>.json`<br>`test_data/output_document_<repo>.md` |
| [`test_github_fetch.py`](test_github_fetch.py) | **Raw API Extractor**. Pulls raw GitHub JSON responses (repo metadata, file tree, issues/PRs). | `test_data/test_github_repo_<repo>.json`<br>`test_data/test_github_tree_<repo>.json`<br>`test_data/test_github_issues_<repo>.json` |
| [`test_github_extraction.py`](test_github_extraction.py) | Entry point forwarding directly to `test_github_fetch.py`. | Same as `test_github_fetch.py` |

---

## 🚀 How to Run

Make sure you are in the workspace root directory:
```bash
cd Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, `index.md`, and `log.md`.

- **Auto-discover and ingest all accessible repos**:
  ```bash
  python backend/connectors/github/tests/test_run_okf.py
  ```
- **Run on specific repository(-ies)**:
  ```bash
  python backend/connectors/github/tests/test_run_okf.py --repo owner/repo
  python backend/connectors/github/tests/test_run_okf.py --repo owner/repo1 --repo owner/repo2
  ```
- **Skip README and/or issues fetching (faster, fewer API calls)**:
  ```bash
  python backend/connectors/github/tests/test_run_okf.py --no-readme --no-issues
  ```

---

### 2. Test the Live GitHub Connector (Intermediate Representation)
Validates connection, ingest repos/issues, and outputs intermediate Document JSON and Markdown.

- **Auto-discover all repos**:
  ```bash
  python backend/connectors/github/tests/test_run_connector.py
  ```
- **Run on specific repository(-ies)**:
  ```bash
  python backend/connectors/github/tests/test_run_connector.py --repo owner/repo
  python backend/connectors/github/tests/test_run_connector.py --repo owner/repo1 --repo owner/repo2
  ```
- **Skip README and/or issues**:
  ```bash
  python backend/connectors/github/tests/test_run_connector.py --no-readme --no-issues
  ```

---

### 3. Fetch Raw GitHub API Payloads (Debugging / Offline Testing)
Fetches raw GitHub API responses to inspect low-level structures or save test fixtures.

- **Interactive Menu Mode**:
  ```bash
  python backend/connectors/github/tests/test_github_fetch.py
  ```
- **Fetch repo metadata only**:
  ```bash
  python backend/connectors/github/tests/test_github_fetch.py --option repo --repo owner/repo
  ```
- **Fetch file tree only**:
  ```bash
  python backend/connectors/github/tests/test_github_fetch.py --option tree --repo owner/repo
  ```
- **Fetch issues/PRs only**:
  ```bash
  python backend/connectors/github/tests/test_github_fetch.py --option issues --repo owner/repo
  ```
- **Fetch all at once**:
  ```bash
  python backend/connectors/github/tests/test_github_fetch.py --option both --repo owner/repo
  ```

> `test_github_extraction.py` is an alias for `test_github_fetch.py`; run it the same way.

---

## 💾 Where the Data is Stored

All test outputs and generated files are saved inside **`backend/connectors/github/test_data/`**:

```
backend/connectors/github/test_data/
│
├── okf_bundle/                        <-- OKF v0.2 Knowledge Bundle
│   ├── index.md                       <-- Directory listing for Progressive Disclosure (§8)
│   ├── log.md                         <-- Chronological update history (§9)
│   ├── <repo_slug>.okf.md             <-- Concept document (YAML Frontmatter + Markdown Body)
│   └── <repo_slug>.okf.json           <-- Machine-readable JSON schema (for Vector DB / Neo4j)
│
├── output_document_<repo>.json        <-- Intermediate structured Document JSON per repo
├── output_document_<repo>.md          <-- Rendered Markdown document preview per repo
│
├── test_github_repo_<repo>.json       <-- Raw GitHub repo metadata payload
├── test_github_tree_<repo>.json       <-- Raw GitHub file tree payload
└── test_github_issues_<repo>.json     <-- Raw GitHub issues / pull requests payload
```

---

## ⚙️ Prerequisites (.env Configuration)

Ensure your `.env` file at the root of the project contains:

```env
GITHUB_TOKEN="github_pat_xxx_your_personal_access_token"
```

Create a fine-grained **Personal Access Token** at:
https://github.com/settings/tokens

For a knowledge/retrieval system, request **read-only** access to `Contents`, `Metadata`, and `Issues`.
