# Notion Connector - Test Suite & Execution Guide

This directory contains test runners, extractors, and verification scripts for the **Notion Connector** and the **Open Knowledge Format (OKF v0.2)** pipeline.

---

## 📁 File-by-File Breakdown

| Script File | Purpose | Main Output / Result |
|:---|:---|:---|
| [`test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_run_okf.py) | **End-to-End OKF v0.2 Bundle Generator**. Ingests Notion pages and builds a complete, standardized Knowledge Bundle. | `test_data/okf_bundle/` (`.okf.md`, `.okf.json`, `index.md`, `log.md`) |
| [`test_run_connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_run_connector.py) | **Live Connector & Normalization Runner**. Runs `NotionConnector` and generates intermediate structured JSON and rendered Markdown. | `test_data/output_document.json`<br>`test_data/output_document.md` |
| [`test_notion_fetch.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_fetch.py) | **Raw API Extractor**. Pulls raw Notion JSON responses (root block, recursive children, database queries). | `test_data/test_notion_block.json`<br>`test_data/test_notion_children.json` |
| [`test_notion_extraction.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_extraction.py) | Entry point forwarding directly to `test_notion_fetch.py`. | Same as `test_notion_fetch.py` |
| [`test_notion_handling.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_handling.py) | Initial inspection script used to explore raw Notion block structures. | Console inspection |

---

## 🚀 How to Run

Make sure you are in the workspace root directory:
```bash
cd /Users/ompatil/Desktop/Enterprise-Knowledge-Agent
```

### 1. Generate & Test the OKF v0.2 Knowledge Bundle (Recommended)
Generates full OKF v0.2 concept files with YAML frontmatter, footnote citations, `index.md`, and `log.md`.

- **Run on default page (from `.env`)**:
  ```bash
  python backend/connectors/notion/tests/test_run_okf.py
  ```
- **Run on a specific Page ID**:
  ```bash
  python backend/connectors/notion/tests/test_run_okf.py --page-id <NOTION_PAGE_UUID>
  ```
- **Auto-discover and ingest entire workspace**:
  ```bash
  python backend/connectors/notion/tests/test_run_okf.py --all
  ```

---

### 2. Test the Live Notion Connector (Intermediate Representation)
Validates connection, parses blocks/charts, and outputs intermediate Document JSON and Markdown.

- **Run on default page**:
  ```bash
  python backend/connectors/notion/tests/test_run_connector.py
  ```
- **Run on all workspace pages**:
  ```bash
  python backend/connectors/notion/tests/test_run_connector.py --all
  ```

---

### 3. Fetch Raw Notion API Payloads (Debugging / Offline Testing)
Fetches raw Notion API responses to inspect low-level block structures or save test fixtures.

- **Interactive Menu Mode**:
  ```bash
  python backend/connectors/notion/tests/test_notion_fetch.py
  ```
- **Fetch root block only**:
  ```bash
  python backend/connectors/notion/tests/test_notion_fetch.py --option block
  ```
- **Fetch all children recursively**:
  ```bash
  python backend/connectors/notion/tests/test_notion_fetch.py --option children
  ```
- **Fetch both at once**:
  ```bash
  python backend/connectors/notion/tests/test_notion_fetch.py --option both
  ```

---

## 💾 Where the Data is Stored

All test outputs and generated files are saved inside **`backend/connectors/notion/test_data/`**:

```
backend/connectors/notion/test_data/
│
├── okf_bundle/                        <-- OKF v0.2 Knowledge Bundle
│   ├── index.md                       <-- Directory listing for Progressive Disclosure (§8)
│   ├── log.md                         <-- Chronological update history (§9)
│   ├── <concept_name>.okf.md          <-- Concept document (YAML Frontmatter + Markdown Body)
│   └── <concept_name>.okf.json        <-- Machine-readable JSON schema (for Vector DB / Neo4j)
│
├── output_document.json               <-- Intermediate structured Document JSON
├── output_document.md                 <-- Rendered Markdown document preview
│
├── test_notion_block.json             <-- Raw Notion page/block API payload
└── test_notion_children.json          <-- Raw Notion child blocks and database rows payload
```

---

## ⚙️ Prerequisites (.env Configuration)

Ensure your `.env` file at the root of the project contains:

```env
NOTION_TOKEN="secret_your_notion_integration_token"
NOTION_PAGE_ID="2fb3317c-c712-8028-80ea-cdca6646fe1e"
```
