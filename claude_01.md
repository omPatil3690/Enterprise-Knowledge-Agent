# Enterprise Knowledge Agent - Change Log Part 2 (Connectors)

This document continues the chronological record maintained in [`claude.md`](claude.md) (Steps 1-31). It documents the GitHub and Dropbox connector work. Future AI models and developers should refer to `claude.md` first, then continue here, to understand design decisions, trace system evolution, or revert/reproduce specific steps.

---

## Metadata
- **Author / Engineer:** Om Patil
- **Project:** Enterprise Knowledge Agent
- **Initial Date:** 2026-08-20
- **Timezone:** IST (+05:30)
- **Previous Log:** [`claude.md`](claude.md) (Steps 1-31)

---

## Step 32: GitHub Connector Architecture & Client (`client.py`)
- **Date:** 2026-08-30
- **Purpose:** Establish the GitHub HTTP API client layer that fetches repositories, READMEs, file trees, and issues. Uses `requests` directly (GitHub REST API v3) rather than the `PyGithub` SDK to keep dependencies minimal.

### Key Decisions & Rationale:
1. **Plain HTTP via `requests`**: Base URL `https://api.github.com`, `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`.
2. **Core Client Methods**:
   - `test_connection()` / `get_current_user()`: verify token and print authenticated user.
   - `list_repositories()`: discover user-accessible repos (with pagination via `Link` header).
   - `get_repository()`: fetch repo metadata (default branch, language, stars/forks, etc.).
   - `fetch_readme()`: retrieve a repo's README content and decode from base64.
   - `list_issues()`: retrieve issues / pull requests (state-filtered, Link-header pagination).
3. **Rate-Limit & 429 Handling**: On `403` rate-limit or `429`, inspects headers and waits on `Retry-After` before retrying.

### Files Created:
- [`backend/connectors/github/client.py`](backend/connectors/github/client.py)

---

## Step 33: GitHub Parser & Normalization (`parser.py`)
- **Date:** 2026-08-30
- **Purpose:** Convert raw GitHub repository JSON (metadata, README markdown, issues) into the standardized intermediate Document format.

### Key Decisions & Rationale:
1. **Ignored / Binary Filtering**: `readme_is_readable()` skips oversized or binary JSON/compressed payloads; explicit ignored names (`README.md` handled separately).
2. **Repository Normalization**: Folds repo metadata into informative `PARAGRAPH`/`CALLOUT` blocks (description, stars/forks, language, license, default branch, topics).
3. **README Markdown Blocking**: Converts README markdown into semantic blocks using a lightweight row-based parser; preserves code fences and headings.
4. **Issue Normalization**: Each issue becomes metadata + numbered list entries capturing title, state, author, labels, and body.
5. **PREFERRED_TEXT_EXTENSIONS** / **IGNORED_TEXT_EXTENSIONS**: Extension allow/block lists control which files are treated as readable text.

### Files Created:
- [`backend/connectors/github/parser.py`](backend/connectors/github/parser.py)

---

## Step 34: GitHub Connector Orchestrator (`connector.py`, `__init__.py`)
- **Date:** 2026-08-30
- **Purpose:** Implement `GitHubConnector` conforming to `BaseConnector`, orchestrate `GitHubClient`, `parser.py`, and `backend/models/document.py` into a unified interface.

### Key Decisions & Rationale:
1. **BaseConnector Conformance**: `test_connection()`, `load_documents()`, `load_document_by_id()`, and `sync_incremental()`.
2. **Configurable Ingestion**: `include_repos` (explicit list or auto-discovery), `fetch_readme`, `fetch_issues` toggles for API-call control.
3. **Typed Document Bridge**: `dict_to_document()` / `dict_to_content_block()` map normalized dictionaries into strongly-typed `Document`, `DocumentMetadata`, and recursive `ContentBlock` trees.
4. **Registered Globally**: `GitHubConnector` exported from `backend/connectors/github/__init__.py` and `backend/connectors/__init__.py`.

### Files Created / Modified:
- [`backend/connectors/github/connector.py`](backend/connectors/github/connector.py) (Created)
- [`backend/connectors/github/__init__.py`](backend/connectors/github/__init__.py) (Created)
- [`backend/connectors/__init__.py`](backend/connectors/__init__.py) (Updated exports)

---

## Step 35: GitHub Test Runners (`test_run_connector.py`, `test_run_okf.py`)
- **Date:** 2026-08-30
- **Purpose:** Provide CLI runners to execute the live GitHub connector and export both intermediate Documents and OKF v0.2 Knowledge Bundles.

### Key Decisions & Rationale:
1. **Live Runner**: `test_run_connector.py` validates connection, ingests repos/issues, prints block breakdowns, and saves `test_data/output_document_<repo>.json` + `.md`.
2. **OKF Bundle Generator**: `test_run_okf.py` builds OKF v0.2 bundles under `test_data/okf_bundle/` (`.okf.md`, `.okf.json`, `index.md`, `log.md`).
3. **CLI Flags**: `--repo`, `--no-readme`, `--no-issues` for GitHub; repeatable `--repo`.

### Files Created:
- [`backend/connectors/github/tests/test_run_connector.py`](backend/connectors/github/tests/test_run_connector.py)
- [`backend/connectors/github/tests/test_run_okf.py`](backend/connectors/github/tests/test_run_okf.py)

---

## Step 36: GitHub Test Suite Docs & Raw API Data Extractor
- **Date:** 2026-08-30
- **Purpose:** Mirror the Notion connector's debugging tools and documentation for GitHub: a unified test guide and a raw API payload extractor.

### Key Decisions & Rationale:
1. **Raw API Extractor** (`test_github_fetch.py`): pulls repo metadata, file tree, and issues/PRs into `test_data/test_github_repo_<repo>.json`, `test_github_tree_<repo>.json`, `test_github_issues_<repo>.json` for offline inspection.
2. **Alias Entry Point** (`test_github_extraction.py`): forwards to `test_github_fetch.py` (with absolute-import fallback so it runs as a plain script).
3. **Execution Guide** (`tests/README.md`): documents every script, CLI flag, output location, and `.env` prerequisites.

### Files Created:
- [`backend/connectors/github/tests/test_github_fetch.py`](backend/connectors/github/tests/test_github_fetch.py)
- [`backend/connectors/github/tests/test_github_extraction.py`](backend/connectors/github/tests/test_github_extraction.py)
- [`backend/connectors/github/tests/README.md`](backend/connectors/github/tests/README.md)

---

## Step 37: GitHub Live Verification
- **Date:** 2026-08-30
- **Purpose:** Confirm the GitHub connector and raw extractor work end-to-end against the live GitHub API.

### Key Decisions & Rationale:
1. **End-to-End Success**: `test_github_fetch.py --option both` auto-discovered `Aditya25-yadav/2048` and pulled repo metadata (200), file tree (200), and issues (200), saving 3 fixture files to `test_data/`.
2. **Connector Import Check**: All GitHub modules import cleanly; `GitHubConnector` registered.

### Files Created / Modified:
- `backend/connectors/github/test_data/test_github_repo_Aditya25-yadav_2048.json` (untracked)
- `backend/connectors/github/test_data/test_github_tree_Aditya25-yadav_2048.json` (untracked)
- `backend/connectors/github/test_data/test_github_issues_Aditya25-yadav_2048.json` (untracked)

---

## Step 38: Dropbox Connector Architecture & Client (`client.py`)
- **Date:** 2026-08-30
- **Purpose:** Establish the Dropbox HTTP API client layer. Uses `requests` directly against the Dropbox (`api.dropboxapi.com/2`) and content (`content.dropboxapi.com/2`) endpoints, avoiding the `dropbox` SDK dependency.

### Key Decisions & Rationale:
1. **Dual Base URLs**: JSON metadata endpoints on `https://api.dropboxapi.com/2`, file download on `https://content.dropboxapi.com/2`.
2. **Core Client Methods**:
   - `test_connection()` / `get_current_account()`: verify token + print account.
   - `list_folder()`: recursive folder listing with `files/list_folder` cursor pagination.
   - `get_file_metadata()`: single file/folder metadata via `files/get_metadata`.
   - `download_file()`: fetch file bytes with the `Dropbox-API-Result` header quirk and 429 rate-limit handling.
3. **Auth**: `Authorization: Bearer <token>`; token set via `DROPBOX_TOKEN`.

### Files Created:
- [`backend/connectors/dropbox/client.py`](backend/connectors/dropbox/client.py)

---

## Step 39: Dropbox Parser & Normalization (`parser.py`)
- **Date:** 2026-08-30
- **Purpose:** Convert raw Dropbox folder/file metadata and downloaded text content into the standardized intermediate Document format.

### Key Decisions & Rationale:
1. **Text-File Filtering**: `is_text_file()` uses `PREFERRED_TEXT_EXTENSIONS` / `IGNORED_TEXT_EXTENSIONS` / `IGNORED_FILE_NAMES` to decide which files to download and parse.
2. **File Documents**: `normalize_file_document()` builds title, path, size, content blocks from downloaded text (with markdown preserved).
3. **Folder Documents**: `normalize_folder_document()` produces a structured `database` block listing contained files/subfolders (Name, Path, Size, Modified) — mirroring the Notion folder-content table pattern.
4. **Path Normalization**: Strips leading `/` when deriving display titles (`/docs` → `docs`).

### Files Created:
- [`backend/connectors/dropbox/parser.py`](backend/connectors/dropbox/parser.py)

---

## Step 40: Dropbox Connector Orchestrator (`connector.py`, `__init__.py`)
- **Date:** 2026-08-30
- **Purpose:** Implement `DropboxConnector` conforming to `BaseConnector`, orchestrate `DropboxClient`, `parser.py`, and `backend/models/document.py`.

### Key Decisions & Rationale:
1. **BaseConnector Conformance**: `test_connection()`, `load_documents()`, `load_document_by_id()`, `sync_incremental()`.
2. **Walk Options**: `root_path`, `include_folders`, `include_files`, `max_files` control traversal and download volume.
3. **Typed Document Bridge**: `dict_to_document()` / `dict_to_content_block()` map normalized dicts into typed `Document` / `ContentBlock` trees.
4. **Registered Globally**: `DropboxConnector` exported from `backend/connectors/dropbox/__init__.py` and `backend/connectors/__init__.py`.

### Files Created / Modified:
- [`backend/connectors/dropbox/connector.py`](backend/connectors/dropbox/connector.py) (Created)
- [`backend/connectors/dropbox/__init__.py`](backend/connectors/dropbox/__init__.py) (Created)
- [`backend/connectors/__init__.py`](backend/connectors/__init__.py) (Updated exports)

---

## Step 41: Dropbox Test Runners (`test_run_connector.py`, `test_run_okf.py`)
- **Date:** 2026-08-30
- **Purpose:** Provide CLI runners to execute the live Dropbox connector and export intermediate Documents and OKF v0.2 Knowledge Bundles.

### Key Decisions & Rationale:
1. **Live Runner**: `test_run_connector.py` validates connection, walks folders, downloads text files, prints block breakdowns, saves `test_data/output_document_*.json` + `.md` (caps previews after 10 docs).
2. **OKF Bundle Generator**: `test_run_okf.py` builds OKF v0.2 bundles under `test_data/okf_bundle/`.
3. **CLI Flags**: `--path`, `--no-folders`, `--no-files`, `--max-files`.

### Files Created:
- [`backend/connectors/dropbox/tests/test_run_connector.py`](backend/connectors/dropbox/tests/test_run_connector.py)
- [`backend/connectors/dropbox/tests/test_run_okf.py`](backend/connectors/dropbox/tests/test_run_okf.py)

---

## Step 42: Dropbox Test Suite Docs & Raw API Data Extractor
- **Date:** 2026-08-30
- **Purpose:** Mirror the Notion/GitHub debugging tools and documentation for Dropbox.

### Key Decisions & Rationale:
1. **Raw API Extractor** (`test_dropbox_fetch.py`): pulls account metadata, folder listing (recursive, cursor-paginated), and file metadata into `test_data/test_dropbox_account.json`, `test_dropbox_folder.json`, `test_dropbox_metadata_*.json`.
2. **Alias Entry Point** (`test_dropbox_extraction.py`): forwards to `test_dropbox_fetch.py` (absolute-import fallback).
3. **Execution Guide** (`tests/README.md`): documents scripts, CLI flags, output locations, `.env` prerequisites (Dropbox access token from https://www.dropbox.com/developers/apps).

### Files Created:
- [`backend/connectors/dropbox/tests/test_dropbox_fetch.py`](backend/connectors/dropbox/tests/test_dropbox_fetch.py)
- [`backend/connectors/dropbox/tests/test_dropbox_extraction.py`](backend/connectors/dropbox/tests/test_dropbox_extraction.py)
- [`backend/connectors/dropbox/tests/README.md`](backend/connectors/dropbox/tests/README.md)

---

## Step 43: Dropbox Offline Sanity & Token Gating
- **Date:** 2026-08-30
- **Purpose:** Validate the Dropbox parser/converter before live execution and gate runners on token presence.

### Key Decisions & Rationale:
1. **Offline Parser Validation**: `_offline_sanity.py` confirmed `is_text_file`, `normalize_file_document` (markdown + timestamps), and `normalize_folder_document` (structured table) all pass; the temp test file was removed after validation (mirroring the GitHub cleanup).
2. **Token Gating**: `test_run_connector.py` and `test_dropbox_fetch.py` fail fast with a clear message when `DROPBOX_TOKEN` is unset in `.env`, so runners fail gracefully before live API calls.
3. **`.env` / `.env.example`**: Added `DROPBOX_TOKEN=` (empty placeholder) to both files.

### Files Created / Modified:
- [`backend/connectors/dropbox/tests/_offline_sanity.py`](backend/connectors/dropbox/tests/_offline_sanity.py) (Created, then removed)
- [`.env.example`](.env.example) (Added `DROPBOX_TOKEN`)
- [`.env`](.env) (Added empty `DROPBOX_TOKEN`)

---

## Step 44: Canonical GitHub & Dropbox Domain Models (`backend/models/github.py`, `backend/models/dropbox.py`)
- **Date:** 2026-08-30
- **Purpose:** Add dedicated, provider-independent domain models for the GitHub and Dropbox connectors in `backend/models/`, mirroring the canonical `EmailDocument`/`EmailAttachment` pattern. Previously these connectors built typed `Document` objects directly from normalized dicts without a domain model layer.

### Key Decisions & Rationale:
1. **Canonical Models with `to_intermediate_document()`**:
   - `backend/models/github.py`: `GitHubRepository` (+ `from_api()` factory), `GitHubIssue`, `GitHubFile`. `GitHubRepository.to_intermediate_document()` renders repo metadata as a `CALLOUT`, README as paragraphs, issues as heading+paragraph trees, and repo metrics as a structured `DATABASE` block (drives OKF `structured_data` extraction).
   - `backend/models/dropbox.py`: `DropboxFile`, `DropboxFolder`, `DropboxEntry` (with `as_table_row()`). File models render heading `File:`/content paragraphs; folder models render heading `Folder:`/summary plus a structured `DATABASE` "Folder Contents" table.
2. **Single Source of Truth**: The connectors now build canonical models via `from_api()` factories and call `to_intermediate_document()`, instead of emitting raw dicts — the same pattern Email/Gmail uses.
3. **Centralized Exports**: Exported `GitHubRepository`, `GitHubIssue`, `GitHubFile`, `DropboxFile`, `DropboxFolder`, `DropboxEntry` from `backend/models/__init__.py`.
4. **Verified**: Offline sanity confirms both models produce correctly structured, markdown-renderable `Document` objects (repo metrics table, folder contents table) and all connectors import cleanly.

### Files Created / Modified:
- [`backend/models/github.py`](backend/models/github.py) (Created)
- [`backend/models/dropbox.py`](backend/models/dropbox.py) (Created)
- [`backend/models/__init__.py`](backend/models/__init__.py) (Updated exports)
- [`backend/connectors/github/connector.py`](backend/connectors/github/connector.py) (Use `GitHubRepository.to_intermediate_document()`)
- [`backend/connectors/dropbox/connector.py`](backend/connectors/dropbox/connector.py) (Use `DropboxFile`/`DropboxFolder.to_intermediate_document()`)

---

## Blocked / Pending
- **Dropbox Live Run**: Cannot execute the live Dropbox runner without a real `DROPBOX_TOKEN`. The user must supply a Dropbox access token (https://www.dropbox.com/developers/apps → create app → generate access token) and set `DROPBOX_TOKEN` in `.env`, then run:
  ```bash
  python backend/connectors/dropbox/tests/test_run_connector.py --max-files 50
  python backend/connectors/dropbox/tests/test_run_okf.py
  ```
- **GitHub Live OKF**: GitHub live fetch/connector verified; OKF bundle generation can also be re-run with `GITHUB_TOKEN` set.

--- 

## Note on Credential Security
As captured in previous steps and re-flagged here: real API keys/tokens are present in tracked `.env.example` and git history. Users should rotate any exposed credentials and blank sensitive values in version-controlled example files.
