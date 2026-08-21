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
