# Enterprise Knowledge Agent - Change Log & Architecture History

This document maintains a chronological record of all architectural decisions, code changes, and iterations performed on the Enterprise Knowledge Agent codebase. Future AI models and developers should refer to this document to understand design decisions, trace system evolution, or revert/reproduce specific steps.

---

## Metadata
- **Author / Engineer:** Om Patil
- **Project:** Enterprise Knowledge Agent
- **Initial Date:** 2026-08-20
- **Timezone:** IST (+05:30)

---

## Step 1: Intermediate Document Model Design
- **Date:** 2026-08-20
- **Time:** 18:54:33 IST
- **Purpose:** Establish the intermediate structured document schema bridging raw source platform JSON (Notion, Confluence, Jira, etc.) and downstream stages (OKF normalization, Chunking, Embeddings, Knowledge Graph).

### Key Decisions & Rationale:
1. **Three-Layer Architecture**:
   - **Layer 1 (Page Metadata)**: `DocumentMetadata` retains stable identifier (`id`), title, source URL, timestamps for change tracking/sync, and hierarchy container (`parent_id`). Discards bulky raw API payloads.
   - **Layer 2 (Semantic Blocks)**: `ContentBlock` normalizes platform-specific block types into standard types (`heading_1`, `heading_2`, `paragraph`, `bulleted_list_item`, `to_do`, `code`, `callout`, `quote`). Preserves structural meaning rather than flat text concatenation.
   - **Layer 3 (Source Attribution)**: `to_source_attribution()` links any atomic text chunk back to its source page URL, page ID, and block ID for exact citations and updates.

### Files Created:
- [`backend/models/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/__init__.py)
- [`backend/models/document.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/document.py)

---

## Step 2: Notion Rich Text & Block Normalization Parser
- **Date:** 2026-08-20
- **Time:** 20:24:12 IST
- **Purpose:** Convert raw Notion JSON responses into the standardized intermediate representation.

### Key Decisions & Rationale:
1. **Rich Text Extraction**: `extract_rich_text(rich_text)` extracts all `plain_text` elements, discarding complex formatting tags while preserving readable text.
2. **Block Normalization**: `extract_block(block)` maps Notion block types to internal semantic types and extracts block IDs for citations.
3. **Dual Page Metadata Support**: `extract_page_metadata(page)` seamlessly handles both `/v1/pages/{id}` (title in properties) and `/v1/blocks/{id}` (title in `child_page`).

### Files Created:
- [`backend/connectors/notion/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/parser.py)

---

## Step 3: Separation of Retrieval vs. Normalization (Pagination & Nested Blocks)
- **Date:** 2026-08-20
- **Time:** 20:34:17 IST
- **Purpose:** Decouple network I/O from data parsing and address Notion API pagination and block hierarchy.

### Key Decisions & Rationale:
1. **Single Responsibility**: Network traversal belongs in `NotionClient`; data parsing belongs in `parser.py`.
2. **Cursor Pagination**: `fetch_all_blocks()` uses a `while has_more:` loop with `next_cursor` to ensure multi-page block streams are never truncated.
3. **Recursive DFS for `has_children == True`**: Automatically fetches child blocks for toggles, callouts, and sub-bullets and attaches them under `children: [...]` so normalization receives the complete document tree.

### Files Created / Modified:
- [`backend/connectors/notion/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/client.py) (Created)
- [`backend/connectors/notion/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/parser.py) (Updated to recursively normalize `children`)

---

## Step 4: Unified Test Data Extractor Script
- **Date:** 2026-08-20
- **Time:** 20:51:06 IST
- **Purpose:** Consolidate isolated testing scripts into an interactive, multi-option extractor for local development and inspection.

### Key Decisions & Rationale:
1. **Unified CLI Options**:
   - `block`: Fetches overall block/page metadata to `test_data/test_notion_block.json`.
   - `children`: Fetches all underlying children blocks to `test_data/test_notion_children.json`.
   - `both`: Fetches both objects simultaneously.
2. **Interactive & Non-Interactive**: Supports CLI flags (`--option`, `--page-id`) as well as an interactive terminal prompt.

### Files Created / Modified:
- [`backend/connectors/notion/tests/test_notion_fetch.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_fetch.py) (Created)
- [`backend/connectors/notion/tests/test_notion_extraction.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_extraction.py) (Updated entrypoint)

---

## Step 5: Child Database & Todo List Row Extraction
- **Date:** 2026-08-20
- **Time:** 21:02:49 IST
- **Purpose:** Extract items/tasks from Notion databases (e.g., inline "Todo List" databases) where records are stored as database rows rather than standard block children.

### Key Decisions & Rationale:
1. **Database Querying**: `fetch_database_rows(database_id)` calls `POST /v1/databases/{id}/query` with cursor pagination to retrieve all rows/pages in that database.
2. **Task & Status Normalization**: `parser.py` parses each row's properties (Title and Checkbox/Status), converting them into normalized `to_do` child items under the database block.

### Files Modified:
- [`backend/connectors/notion/tests/test_notion_fetch.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_notion_fetch.py)
- [`backend/connectors/notion/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/parser.py)

---

## Step 6: Filtering Media, Binary Files, and Web Bookmarks
- **Date:** 2026-08-20
- **Time:** 21:22:16 IST
- **Purpose:** Prevent non-textual attachments and links from polluting the text/semantic knowledge pipeline.

### Key Decisions & Rationale:
1. **Explicit Ignored Block Registry**: Defined `IGNORED_BLOCK_TYPES` in `parser.py`:
   - `pdf`, `video`, `audio`, `file`, `bookmark`, `embed`, `image`, `link_preview`, `divider`, `unsupported`.
2. **Early Elimination**: Any block matching an ignored type returns `None` immediately, ensuring downstream chunkers and graph extractors receive clean, high-signal knowledge.

### Files Modified:
- [`backend/connectors/notion/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/parser.py)

---

## Step 7: Abstract Base Connector Contract (`BaseConnector`)
- **Date:** 2026-08-21
- **Time:** 19:06:41 IST
- **Purpose:** Establish a standardized lifecycle contract for all enterprise source connectors (Notion, Confluence, Jira, Slack, Drive).

### Key Decisions & Rationale:
1. **Unified Interface**: Defined `BaseConnector(ABC)` with mandatory abstract methods:
   - `test_connection() -> bool`: Verifies API keys and reachability.
   - `load_documents() -> List[Document]`: Returns full collection of normalized `Document` objects.
   - `load_document_by_id(doc_id) -> Optional[Document]`: Targeted single-document retrieval.
2. **Built-in Incremental Sync Fallback**: `sync_incremental(last_sync_time)` provides timestamp-based filtering over `doc.metadata.last_edited_time` for delta synchronization.

### Files Created:
- [`backend/connectors/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/__init__.py)
- [`backend/connectors/base.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/base.py)

---

## Step 8: Notion Connector Orchestrator & Typed Document Bridge
- **Date:** 2026-08-21
- **Time:** 19:07:39 IST
- **Purpose:** Implement `NotionConnector` to orchestrate `NotionClient`, `parser.py`, and `backend/models/document.py` into a unified interface conforming to `BaseConnector`.

### Key Decisions & Rationale:
1. **End-to-End Orchestrator**: `NotionConnector` provides `test_connection()`, `load_document_by_id()`, `load_documents()`, and `sync_incremental()`.
2. **Workspace Auto-Discovery**: Implemented `POST /v1/search` in `NotionClient.search_pages()` allowing automatic multi-page discovery across the entire workspace without hardcoding single page IDs.
3. **Type-Safe Document Bridge**: `dict_to_document()` maps raw normalized dictionaries into strongly-typed `Document`, `DocumentMetadata`, and recursive `ContentBlock` trees.

### Files Created / Modified:
- [`backend/connectors/notion/connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/connector.py) (Created)
- [`backend/connectors/notion/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/client.py) (Updated with search & test_connection)
- [`backend/models/document.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/document.py) (Updated with recursive markdown rendering and BlockType helper)
- [`backend/connectors/notion/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/__init__.py) (Exported NotionConnector)
- [`backend/connectors/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/__init__.py) (Exported NotionConnector)

---

## Step 9: End-to-End Live Runner & Inspector (`test_run_connector.py`)
- **Date:** 2026-08-21
- **Time:** 19:30:39 IST
- **Purpose:** Provide a dedicated CLI runner to execute the live connector against a Notion page or workspace and save both formatted Markdown and structured JSON outputs.

### Key Decisions & Rationale:
1. **Dual Output Generation**: Saves both `test_data/output_document.json` (for programmatic RAG validation) and `test_data/output_document.md` (for human inspection of rendered document).
2. **Metadata & Block Breakdown Summary**: Displays key statistics in terminal including parent containers, last edited timestamps, and counts per block type.

### Files Created:
- [`backend/connectors/notion/tests/test_run_connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_run_connector.py)

---

## Step 10: Complete Database, Chart & Table Extraction (Schemas & Records)
- **Date:** 2026-08-21
- **Time:** 19:39:42 IST
- **Purpose:** Full structural extraction of Notion databases, charts, metric boards, and tables into structured JSON records and formatted Markdown tables.

### Key Decisions & Rationale:
1. **Rich Property Value Extraction**: Implemented `extract_property_value()` in `parser.py` handling all Notion column types: `number`, `select`, `multi_select`, `date`, `checkbox`, `status`, `formula`, `url`, `email`, `phone_number`, `people`, `relation`.
2. **Tabular Record Representation**: Each database/chart block in `ContentBlock` now contains:
   - `columns`: List of column header names.
   - `rows`: List of records `{"id": row_id, "data": {col_name: typed_value}}`.
   - `properties`: Summary statistics (`total_rows`).
3. **Markdown Table Rendering**: `Document.to_markdown()` converts database and table blocks into clean GitHub-Flavored Markdown tables (`| Col1 | Col2 |` / `| --- | --- |`).

### Files Modified:
- [`backend/connectors/notion/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/parser.py)
- [`backend/models/document.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/document.py)
- [`backend/connectors/notion/connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/connector.py)

---

## Step 11: Open Knowledge Format (OKF v0.2) Specification Implementation
- **Date:** 2026-08-21
- **Time:** 20:28:51 IST
- **Purpose:** Fully align the knowledge representation layer with the official OKF v0.2 Specification (incorporating Provenance, Trust Tiers, Lifecycle, Actor conventions, Footnote Attributions, and Knowledge Bundle index/log generators).

### Key Decisions & Rationale:
1. **Full OKF v0.2 Frontmatter Families**:
   - **Core**: `type` (required), `title`, `description`, `resource`, `tags`.
   - **Trust**: `generated: { by, at }`, `verified: [{ by, at }]` with auto-derived `trust_tier` (`unverified`, `machine-confirmed`, `human-reviewed`).
   - **Lifecycle**: `status` (`draft | stable | deprecated`), `stale_after` timestamp with `is_stale` check.
   - **Provenance**: `sources` list with join keys `id`, `resource`, credibility signals (`author`, `usage_count`, `last_modified`), and `usage_window`.
2. **Footnote-Based Attribution**: Formats citations in Markdown as `[^source-id]` matching `sources[].id`.
3. **Knowledge Bundle Management (`OKFBundle`)**: Supports multi-concept bundles, auto-generating `index.md` (progressive disclosure) and `log.md` (chronological update history).

### Files Created / Modified:
- [`backend/models/okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/okf.py) (Updated to strict OKF v0.2)
- [`backend/models/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/__init__.py) (Exported `OKFConcept`, `OKFBundle`, `OKFSource`, `OKFActor`)

---

## Step 12: End-to-End OKF v0.2 Knowledge Bundle Runner & Output Inspector
- **Date:** 2026-08-21
- **Time:** 22:13:37 IST
- **Purpose:** Build a dedicated CLI runner to ingest Notion pages and export complete OKF v0.2 Knowledge Bundles with `.okf.md`, `.okf.json`, `index.md`, and `log.md` files.

### Key Decisions & Rationale:
1. **Full Bundle Generation**: Saves all concepts into `backend/connectors/notion/test_data/okf_bundle/`.
2. **Progressive Disclosure & History**: Automatically generates `index.md` and `log.md` matching §8 and §9 of the OKF v0.2 Specification.

### Files Created:
- [`backend/connectors/notion/tests/test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_run_okf.py)

---

## Step 13: Test Suite Documentation Guide (`tests/README.md`)
- **Date:** 2026-08-21
- **Time:** 22:18:46 IST
- **Purpose:** Provide a dedicated guide inside the `tests/` directory explaining script purposes, execution commands, and output data locations.

### Key Decisions & Rationale:
1. **Comprehensive Directory Guide**: Documents `test_run_okf.py`, `test_run_connector.py`, and `test_notion_fetch.py`.
2. **Storage Layout**: Clarifies locations for raw JSON fixtures, intermediate document outputs, and OKF v0.2 knowledge bundle artifacts.

### Files Created:
- [`backend/connectors/notion/tests/README.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/README.md)

---

## Step 14: YAML Frontmatter String Escaping & Quote Sanitization
- **Date:** 2026-08-21
- **Time:** 22:29:16 IST
- **Purpose:** Ensure all YAML frontmatter strings (titles, descriptions, source titles) with embedded quotes or special characters are properly escaped with standard YAML/JSON serialization to prevent invalid YAML formatting.

### Key Decisions & Rationale:
1. **JSON-Safe Escaping**: Applied `json.dumps(..., ensure_ascii=False)` to `title`, `description`, and `source.title` fields in `to_okf_markdown()` so embedded double quotes are escaped as `\"` instead of breaking YAML parsers.
2. **Leading/Trailing Quote Trimming**: Automatically cleans leading/trailing quotes when synthesizing automatic descriptions in `from_intermediate_document()`.

### Files Modified:
- [`backend/models/okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/okf.py)

---

## Step 15: Explicit Timestamp & Delta Change Tracking (`created_at`, `updated_at`, `content_hash`)
- **Date:** 2026-08-21
- **Time:** 22:32:47 IST
- **Purpose:** Explicitly record creation and modification timestamps in OKF frontmatter and JSON metadata to support downstream delta change detection, recency scoring, and incremental synchronization.

### Key Decisions & Rationale:
1. **Explicit Frontmatter Timestamps**: Added `created_at` and `updated_at` (derived from Notion's `created_time` and `last_edited_time`) to `OKFConcept`.
2. **Multi-Layer Delta Synchronization**:
   - `content_hash`: SHA-256 hash for byte-level change comparison.
   - `updated_at` / `last_modified`: ISO timestamp for incremental synchronization and recency queries.
   - `verified[].at`: ISO timestamp recording when the sync job confirmed the document.

### Files Modified:
- [`backend/models/okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/okf.py)

---

## Step 16: Verification & Alignment with Official Notion Search OpenAPI Specification
- **Date:** 2026-08-21
- **Time:** 23:16:01 IST
- **Purpose:** Verify and upgrade `search_pages()` against the official Notion `POST /v1/search` OpenAPI 3.1.0 specification.

### Key Decisions & Rationale:
1. **OpenAPI Spec Compliance**:
   - Upgraded `search_pages()` in `NotionClient` to include the standard `sort: {"direction": "descending", "timestamp": "last_edited_time"}` so pages are discovered in order of recency.
   - Configurable `filter_object`: supports filtering by `"page"`, `"data_source"` / `"database"`, or retrieving all shared objects.
   - Strict adherence to pagination (`page_size: 100`, `start_cursor`, `next_cursor`, `has_more`).

### Files Modified:
- [`backend/connectors/notion/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/client.py)

---

## Step 17: Resilient Error Handling & Standard UUID Formatting for Notion Databases
- **Date:** 2026-08-21
- **Time:** 23:56:22 IST
- **Purpose:** Prevent `400 Bad Request` or permissions errors on individual database queries from halting the ingestion of parent pages.

### Key Decisions & Rationale:
1. **Standard Hyphenated UUIDs (`format_uuid`)**: Formats all Notion IDs to standard `8-4-4-4-12` format (`2fb3317c-c712-8165-8fcf-d305c67818ae`) required by Notion endpoints.
2. **Resilient Database Recovery**: In `fetch_database_rows()`, non-200 responses (e.g. linked database views without external permissions or empty data source blocks) log a clean notice and return `[]` instead of raising an uncaught exception, allowing the parent page and all its other content to finish loading seamlessly.

### Files Modified:
- [`backend/connectors/notion/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/client.py)

---

## Step 18: Unfiltered Workspace Discovery & Item Enumeration Logging
- **Date:** 2026-08-22
- **Time:** 00:02:46 IST
- **Purpose:** Ensure all objects (pages, wikis, root databases) are discovered without restrictive filters, and print explicit discovery summaries during test runs.

### Key Decisions & Rationale:
1. **Default `filter_object=None`**: Changed `search_pages()` default to `None` so Notion returns all shared assets across the workspace without omitting non-page types.
2. **Terminal Enumeration**: `test_run_okf.py` now prints every discovered item name, type, and ID to clearly show which pages are visible to the connection token.

### Files Modified:
- [`backend/connectors/notion/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/client.py)
- [`backend/connectors/notion/tests/test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/notion/tests/test_run_okf.py)

---

## Step 19: Untrack Test Data Directories & Comprehensive .gitignore Configuration
- **Date:** 2026-08-23
- **Time:** 22:54:19 IST
- **Purpose:** Ensure local test data, test JSON payloads, and generated OKF bundle artifacts are untracked by Git while preserved locally on disk.

### Key Decisions & Rationale:
1. **Git Index Cache Removal**: Executed `git rm -r --cached` on `backend/connectors/notion/test_data/` to remove tracked artifacts from Git staging while preserving local files on disk.
2. **Comprehensive .gitignore**: Added `test_data/`, `**/test_data/`, `*.okf.md`, `*.okf.json`, Python cache, and virtual environment patterns to `.gitignore`.

### Files Modified:
- [`.gitignore`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/.gitignore)

---

## Step 20: Environment Configuration Template (`.env.example`)
- **Date:** 2026-08-23
- **Time:** 22:59:48 IST
- **Purpose:** Provide a clean, documented template for environment variables across connectors (Notion, Confluence, Jira, GitHub, Slack), LLM providers (Gemini, OpenAI), Vector stores (Qdrant, Chroma), and Neo4j Knowledge Graph.

### Key Decisions & Rationale:
1. **Clear Modular Sections**: Structured with clear headings and links to developer setup portals for rapid onboarding.

### Files Created:
- [`.env.example`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/.env.example)

---

## Step 21: OAuth Secrets & Credential Exclusion in .gitignore
- **Date:** 2026-08-25
- **Time:** 13:33:33 IST
- **Purpose:** Secure sensitive OAuth tokens (`token.json`, `credentials.json`, `client_secret*.json`, `service_account*.json`) used by Gmail/Google OAuth across all subdirectories from being tracked in Git.

### Key Decisions & Rationale:
1. **Glob Patterns for Nested Secrets**: Added `credentials.json`, `**/credentials.json`, `token.json`, `**/token.json`, `*.token.json`, `client_secret*.json`, and `service_account*.json` to `.gitignore`.

### Files Modified:
- [`.gitignore`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/.gitignore)

---

## Step 22: Gmail Connector Setup & OAuth 2.0 Guide Documentation
- **Date:** 2026-08-25
- **Time:** 14:20:33 IST
- **Purpose:** Document step-by-step setup, configuration of Google Cloud OAuth consent, test users, `gmail.readonly` scope, and local execution flow.

### Key Decisions & Rationale:
1. **Least-Privilege Security**: Enforced `https://www.googleapis.com/auth/gmail.readonly` over full mail access.
2. **Complete Reference Guide**: Provided an in-depth reference inside `backend/connectors/email/gmail/README.md` covering Google Cloud Project creation, OAuth client setup, downloading `credentials.json`, installing libraries, and running `test_gmail.py`.

### Files Created:
- [`backend/connectors/email/gmail/README.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/README.md)

---

## Step 23: Centralized Documentation Directory (`documents.md`)
- **Date:** 2026-08-25
- **Time:** 14:27:49 IST
- **Purpose:** Provide a centralized directory of all official external documentation, API references, developer consoles, and credential creation portals across all supported connectors, AI providers, and vector/graph databases.

### Key Decisions & Rationale:
1. **Comprehensive Directory Organization**: Organized into 6 structured sections: Email/Gmail, Notion, Atlassian (Confluence/Jira), Code/Collaboration (GitHub/Slack/Drive), LLM Providers (Gemini/OpenAI/Anthropic), and Databases (Qdrant/Chroma/Neo4j).

### Files Created:
- [`documents.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/documents.md)

---

## Step 24: Silent JSON Payload Export in `test_gmail.py`
- **Date:** 2026-08-25
- **Time:** 14:31:21 IST
- **Purpose:** Redirect all Gmail API responses and raw message payloads directly into `backend/connectors/email/gmail/test_data/` instead of dumping sensitive emails into the terminal output.

### Key Decisions & Rationale:
1. **File-Based Output Redirection**:
   - `inbox_messages_list.json`: Saved raw result from `messages.list(maxResults=5)`.
   - `message_{id}.json`: Saved individual full message payloads.
   - `all_sample_messages.json`: Saved complete batch of message data.
2. **Clean Terminal Reporting**: Terminal only displays authentication status and generated output file paths.

### Files Modified:
- [`backend/connectors/email/gmail/tests/test_gmail.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_gmail.py)

---

## Step 25: Canonical Email Document Models (`EmailDocument`, `EmailAttachment`)
- **Date:** 2026-08-25
- **Time:** 14:54:44 IST
- **Purpose:** Establish provider-independent email data models bridging raw email APIs (Gmail, Outlook, IMAP) to the system's intermediate Document format.

### Key Decisions & Rationale:
1. **Provider-Agnostic Schema**: Defined `EmailDocument` and `EmailAttachment`.
2. **Seamless Intermediate Bridge (`to_intermediate_document()`)**:
   - Maps email headers into a clean `CALLOUT` block (`✉️`).
   - Maps subject into a `HEADING_2` block.
   - Parses email body text into semantic `PARAGRAPH` blocks.
   - Attaches files into structured bullet list blocks with `📎` citations.
   - Sets `parent_type="thread"` and `parent_id=thread_id` to preserve conversation relationships in downstream Graph RAG.

### Files Created:
- [`backend/models/email.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/email.py)

---

## Step 26: Centralized Global Models Layout (`backend/models/email.py`)
- **Date:** 2026-08-25
- **Time:** 18:35:51 IST
- **Purpose:** Centralize all domain data models inside `backend/models/` for unified global model management across the entire codebase.

### Key Decisions & Rationale:
1. **Global Models Packaging**: Placed `EmailDocument` and `EmailAttachment` in `backend/models/email.py` and exported them directly from `backend/models/__init__.py`.
2. **Clean Connector Interface**: `backend/connectors/email/__init__.py` re-exports from `backend.models.email`.

### Files Created / Modified:
- [`backend/models/email.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/email.py) (Created)
- [`backend/models/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/__init__.py) (Updated exports)
- [`backend/connectors/email/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/__init__.py) (Updated imports)

---

## Step 27: Recursive Gmail MIME & Payload Parser (`parser.py`)
- **Date:** 2026-08-25
- **Time:** 18:38:10 IST
- **Purpose:** Implement recursive traversal of complex nested MIME email payloads (multipart/alternative, multipart/mixed), base64 decoding, header extraction, HTML cleanup, and conversion to canonical `EmailDocument`.

### Key Decisions & Rationale:
1. **Recursive DFS for MIME Trees**: Traverses all nested child parts in `_extract_mime_parts_recursive()` to cleanly separate `text/plain`, `text/html`, and attachments.
2. **URL-Safe Base64 Padding Repair**: `decode_base64url()` automatically normalizes `-` / `_` and adds `=` padding before decoding.
3. **HTML Sanitization Fallback**: `clean_html_to_text()` converts HTML tags to readable text when plaintext bodies are omitted.
4. **Validation Test Suite**: Created `backend/connectors/email/gmail/tests/test_parser.py` and verified 100% successful parsing across real Gmail payloads.

### Files Created:
- [`backend/connectors/email/gmail/parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/parser.py)
- [`backend/connectors/email/gmail/tests/test_parser.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_parser.py)

---

## Step 28: Update Pending Notes for Email Attachments (`NOTES.md`)
- **Date:** 2026-08-25
- **Time:** 18:43:07 IST
- **Purpose:** Record pending task in `NOTES.md` for multimodal media, OCR, and binary attachment parsing for the Email/Gmail connector.

### Key Decisions & Rationale:
1. **Tracking Future Media Parsers**: Documented that OCR and multimodal attachment extraction (PDFs, images, audio, video) will be implemented as specialized extractors.

### Files Modified:
- [`NOTES.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/NOTES.md)

---

## Step 29: Gmail Client & BaseConnector Implementation (`client.py` & `connector.py`)
- **Date:** 2026-08-25
- **Time:** 18:58:35 IST
- **Purpose:** Implement `GmailClient` and `GmailConnector` conforming to `BaseConnector` for connection verification, full message ingestion, single email lookup, and incremental synchronization.

### Key Decisions & Rationale:
1. **BaseConnector Conformance**: Implemented `test_connection()`, `load_documents()`, `load_document_by_id()`, and `sync_incremental()`.
2. **Batch Retrieval & Paging**: `fetch_messages_batch()` in `GmailClient` automatically paginates through `users.messages.list` and retrieves full MIME payloads via `users.messages.get`.
3. **Live Verification**: Created `backend/connectors/email/gmail/tests/test_run_connector.py` and successfully tested live inbox ingestion with intermediate Document generation and Markdown rendering.

### Files Created / Modified:
- [`backend/connectors/email/gmail/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/client.py) (Created)
- [`backend/connectors/email/gmail/connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/connector.py) (Created)
- [`backend/connectors/email/gmail/tests/test_run_connector.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_run_connector.py) (Created)
- [`backend/connectors/email/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/__init__.py) (Updated exports)
- [`backend/connectors/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/__init__.py) (Updated exports)

---

## Step 30: End-to-End OKF v0.2 Knowledge Bundle Runner for Gmail (`test_run_okf.py`)
- **Date:** 2026-08-25
- **Time:** 20:12:41 IST
- **Purpose:** Implement end-to-end OKF v0.2 Knowledge Bundle generation for Gmail, saving individual `.okf.md`, `.okf.json`, progressive disclosure `index.md`, and chronological `log.md`.

### Key Decisions & Rationale:
1. **Dynamic Platform Provenance**: Upgraded `from_intermediate_document()` in `backend/models/okf.py` to dynamically attribute provenance sources (`gmail://messages/{id}`), verification processes (`process:gmail-sync`), and titles.
2. **Complete Knowledge Bundle Export**: Generates full OKF v0.2 bundles inside `backend/connectors/email/gmail/test_data/okf_bundle/`.
3. **Test Suite Documentation**: Created `backend/connectors/email/gmail/tests/README.md` documenting all test runners and data directories.

### Files Created / Modified:
- [`backend/connectors/email/gmail/tests/test_run_okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/test_run_okf.py) (Created)
- [`backend/connectors/email/gmail/tests/README.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/email/gmail/tests/README.md) (Created)
- [`backend/models/okf.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/okf.py) (Updated platform provenance)

---

## Step 31: Comprehensive Test Suite Documentation (`backend/connectors/email/gmail/tests/README.md`)
- **Date:** 2026-08-25
- **Time:** 20:18:32 IST
- **Purpose:** Provide an in-depth, file-by-file testing reference and command cheat sheet for all Gmail connector test runners, MIME validators, payload extractors, and output data directories.

### Key Decisions & Rationale:
1. **Complete File Matrix**: Documented all 4 test scripts (`test_run_okf.py`, `test_run_connector.py`, `test_parser.py`, `test_gmail.py`) with input arguments, purpose, and generated output files.
2. **Directory Layout Guide**: Outlined the complete storage layout under `backend/connectors/email/gmail/test_data/`.

---

## Step 32: System-Wide Documentation Synchronization & Formatting (`DOCUMENTS.md`)
- **Date:** 2026-09-03
- **Time:** 18:57:30 IST
- **Purpose:** Restructure and format `DOCUMENTS.md` with complete, properly aligned Markdown tables, GitHub alert blocks, a table of contents, and all official developer portal/API reference links.

### Key Decisions & Rationale:
1. **Clear Navigation & Structure**: Added an indexed Table of Contents covering 9 distinct categories:
   - Email (Gmail & Workspace), Cloud Storage (Dropbox & Drive), Notion, Atlassian (Confluence & Jira), Code (GitHub), Collaboration (Slack), AI/LLMs (Gemini, OpenAI, Claude), Databases (Qdrant, ChromaDB, Neo4j), and Parsing Engines (PyPDF, python-docx, openpyxl).
2. **Standardized Formatting**: Enforced clean GitHub-Flavored Markdown tables with explicit columns (`Resource`, `Description`, `Official URL`) and clickable external links.
3. **Security & Implementation Notes**: Integrated GitHub callout blocks (`> [!NOTE]`, `> [!TIP]`) highlighting least-privilege scopes and token lifecycle rules.

### Files Modified:
- [`DOCUMENTS.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/DOCUMENTS.md)

---

## Step 33: Comprehensive Markdown Representation & Formatting (`RESEARCH.md`)
- **Date:** 2026-09-03
- **Time:** 23:04:45 IST
- **Purpose:** Format `RESEARCH.md` into clean GitHub-Flavored Markdown without altering section ordering, sequence, or substantive content.

### Key Decisions & Rationale:
1. **Diagram & Schema Encapsulation**: Enclosed all unformatted ASCII flowcharts, tree structures, and architecture diagrams in explicit ````text ... ```` code fences with complete root and footer boundaries.
2. **Payload Syntax Highlighting**: Wrapped raw JSON response payloads and data dictionaries in ````json ... ```` fences, and Python client API calls in ````python ... ```` fences.
3. **Tabular Data Conversion**: Formatted pseudo-tables (e.g. metadata sync tables, question-type vs retrieval mechanism matrix) into aligned GitHub-Flavored Markdown tables.
4. **Header Separation**: Fixed inline accidental concatenations (e.g. `me → authenticated Gmail account 7. What are query parameters?`) into clean standalone markdown section headings (`## 7. What are query parameters?`).
5. **Content Integrity**: Verified 100% balanced code fences (370 total) and verified that all 105 headings and core content blocks maintain the exact chronological research sequence.

### Files Modified:
- [`RESEARCH.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/RESEARCH.md)

---

## Step 34: Graph Entity & Relationship Models (`backend/models/graph.py`)
- **Date:** 2026-09-04
- **Time:** 14:38 IST
- **Purpose:** Create the canonical graph data model layer for the GitHub knowledge graph stored in Neo4j. This is Step 1 of the Graph RAG pipeline (Models → Extractor → Neo4j Client → RAG).

### Key Decisions & Rationale:
1. **Two-enum registry**: `NodeLabel` (Repository, File, User, Team, Issue, PullRequest, Commit, Label) and `RelType` (12 relationship types) as single source of truth for all Neo4j labels and relationship type strings.
2. **Stable namespaced node_id**: Every node has a `node_id` in format `github:<type>:<key>` used as the Neo4j MERGE key for idempotent upserts.
3. **from_api() parsers**: Every typed node has a `@classmethod from_api()` that defensively parses the raw GitHub REST API JSON, including all nested objects (owner, head, base, reactions, verification, etc.).
4. **Relationship-driven lists excluded from node properties**: `assignee_logins`, `label_names`, `added_files` etc. are kept on the typed node for extractor use but excluded from `to_graph_node()` — they become edges (:ASSIGNED_TO, :TAGGED_WITH, :MODIFIES) in the graph.
5. **GitHubGraphBundle**: Container for all nodes and relationships from one repo pass. Provides `all_nodes()` and `summary()`.

### Files Created:
- [`backend/models/graph.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/models/graph.py) — **[NEW]**

---

## Step 35: GitHub Graph Extractor (`backend/graph/github_extractor.py`)
- **Date:** 2026-09-04
- **Time:** 15:30 IST
- **Purpose:** Step 2 of Graph RAG pipeline. Extracts a `GitHubGraphBundle` from a live GitHub repository using the `GitHubClient`, producing all typed nodes and `GraphRelationship` edges ready for Neo4j ingestion.

### Key Decisions & Rationale:
1. **User deduplication via dict**: Users accumulate in a `Dict[str, UserNode]` keyed by `node_id`. Same user appearing as issue author, PR author, and commit author is stored only once.
2. **Relationship-first design**: For each entity fetched, relationships are built inline at extraction time (CREATED, ASSIGNED_TO, REVIEWED, TAGGED_WITH, AUTHORED, CLOSES) rather than in a second pass.
3. **`_CLOSES_RE` regex**: Parses `Closes #N`, `Fixes #N`, `Resolves #N` patterns from PR body text to produce `PullRequest -[:CLOSES]-> Issue` edges automatically.
4. **`_EXT_LANGUAGE` map**: Enriches `FileNode.language` from file extension at extraction time (20+ extensions mapped).
5. **`max_files` / `max_commits` caps**: Guards against hammering the API on large repos. Defaults: 1000 files, 200 commits.
6. **Graceful skips**: Issues=0 PRs=0 on a clean repo → no crash. Teams always skipped with clear message (needs org-level token).
7. **Two new `GitHubClient` methods added**: `list_pull_requests()` (uses `/pulls` endpoint for PR-specific fields: head/base SHA+ref, draft, requestedReviewers) and `list_commits()` (with `max_count` cap).

### Live Test Result (omPatil3690/Enterprise-Knowledge-Agent):
- 1 Repository, 2 Users, 59 Files, 31 Commits, 91 Relationships
- Relationship types: `OWNED_BY ×1`, `CONTAINS ×59`, `AUTHORED ×31`

### Files Created/Modified:
- [`backend/graph/__init__.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/graph/__init__.py) — **[NEW]** package init
- [`backend/graph/github_extractor.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/graph/github_extractor.py) — **[NEW]** extractor
- [`backend/connectors/github/client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/connectors/github/client.py) — **[MODIFIED]** added `list_pull_requests()` and `list_commits()`

### Next Step:
- Step 36: `backend/graph/neo4j_client.py` — take the `GitHubGraphBundle` and MERGE nodes/edges into Neo4j.

## Step 36: Neo4j Graph Client (`backend/graph/neo4j_client.py`)
- **Date:** 2026-09-07
- **Time:** 19:50 IST
- **Purpose:** Step 3 of Graph RAG pipeline. Takes a `GitHubGraphBundle` from the extractor and writes all nodes and relationships into Neo4j using idempotent MERGE queries.

### Key Decisions & Rationale:
1. **MERGE on node_id** — re-running ingestion updates existing nodes (`SET n += props`) instead of creating duplicates. Safe to run on every sync.
2. **UNWIND batching** — sends one Cypher query per node-label group (not one query per node). Default batch size 500. Dramatically reduces round-trips on large repos.
3. **Group by label/type** — Cypher cannot use dynamic labels or relationship types, so nodes are grouped by `NodeLabel` and relationships by `RelType`, with a pre-built template dict for each.
4. **MATCH for relationship endpoints** — if either end of a relationship doesn't exist (e.g. CLOSES pointing to an issue outside the bundle), Neo4j silently skips that row.
5. **`_sanitize_properties()`** — strips None, JSON-stringifies nested dicts, keeps list[primitive] as-is. Neo4j does not support nested dict properties.
6. **`create_constraints()` + `create_indexes()`** — uniqueness constraint on `node_id` for every label, plus lookup indexes on `login`, `path`, `sha`, `number`, `full_name`.
7. **`neo4j==6.3.0`** added to `requirements.txt`.
8. **`__main__` block** — runnable directly: `python3 backend/graph/neo4j_client.py --repo owner/name --query`.

### Files Created/Modified:
- [`backend/graph/neo4j_client.py`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/backend/graph/neo4j_client.py) — **[NEW]**
- [`requirements.txt`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/requirements.txt) — `neo4j==6.3.0` added

### Next Step:
- Step 37: End-to-end live test — run `neo4j_client.py` against a real Neo4j instance.
