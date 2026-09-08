# Jira Connector - Test Suite & Execution Guide

This directory contains test runners and verification scripts for the **Jira Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
|:---|:---|:---|
| [`test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/jira/tests/test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Ingests Jira projects/issues and builds a complete, standardized Knowledge Bundle. | `test_data/okf_bundle/` (`.okf.md`, `.okf.json`, `index.md`, `log.md`) |
| [`test_run_connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/jira/tests/test_run_connector.py) | **Live Connector & Normalization Runner**. Runs `JiraConnector`, parses ADF descriptions, and generates intermediate structured JSON + rendered Markdown. | `test_data/output_document_*.json`<br>`test_data/output_document_*.md` |

---

## 🚀 How to Run

Make sure you are in the workspace root directory:
```bash
cd /Users/ompatil/Desktop/Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, `index.md`, and `log.md`.

- **Run on all projects**:
  ```bash
  python backend/connectors/jira/tests/test_run_okf.py
  ```
- **Run on specific projects (comma-separated)**:
  ```bash
  python backend/connectors/jira/tests/test_run_okf.py --projects ENG,PROJ
  ```
- **Limit issues fetched per project**:
  ```bash
  python backend/connectors/jira/tests/test_run_okf.py --max-issues 50
  ```

---

### 2. Test the Live Jira Connector (Intermediate Representation)
Validates connection, parses ADF descriptions, and outputs intermediate Document JSON and Markdown.

- **Run on all projects**:
  ```bash
  python backend/connectors/jira/tests/test_run_connector.py
  ```
- **Run on specific projects**:
  ```bash
  python backend/connectors/jira/tests/test_run_connector.py --projects ENG,PROJ
  ```

---

## 💾 Where the Data is Stored

All test outputs and generated files are saved inside **`backend/connectors/jira/test_data/`**:

```
backend/connectors/jira/test_data/
│
├── okf_bundle/                        <-- OKF v0.2 Knowledge Bundle
│   ├── index.md                       <-- Directory listing for Progressive Disclosure (§8)
│   ├── log.md                         <-- Chronological update history (§9)
│   ├── <concept_name>.okf.md          <-- Concept document (YAML Frontmatter + Markdown Body)
│   └── <concept_name>.okf.json        <-- Machine-readable JSON schema (for Vector DB / Neo4j)
│
├── output_document_<issue>.json       <-- Intermediate structured Document JSON
└── output_document_<issue>.md         <-- Rendered Markdown document preview
```

---

## ⚙️ Prerequisites (.env Configuration)

Ensure your `.env` file at the root of the project contains:

```env
JIRA_URL="https://your-domain.atlassian.net"
JIRA_USERNAME="your-email@company.com"
JIRA_API_TOKEN="your_jira_api_token"
```

> **Note:** Jira Cloud requires an API token generated at
> [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
> Use your account e-mail as `JIRA_USERNAME` — never your Atlassian password.

> **⚠️ `JIRA_URL` pitfall:** it must point to the **actual Jira site the token was issued for**
> (e.g. `https://your-org.atlassian.net`). Do **not** use `https://home.atlassian.com` —
> that account portal returns an HTML page with HTTP 200, so the connection test can pass
> while project/issue payloads fail to parse JSON (a silent failure).

---

## 🔐 Required Jira Permissions

The connector relies on read-only REST endpoints. The API token only needs access
to projects the account can already browse:

- `GET /rest/api/3/myself` (connection test)
- `GET /rest/api/3/project` (project discovery)
- `GET /rest/api/3/search` (JQL issue search with `startAt` pagination)
- `GET /rest/api/3/issue/{key}` (single issue with ADF description)