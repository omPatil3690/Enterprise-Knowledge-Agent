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
