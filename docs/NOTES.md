# This markdown file is for maintaining personal notes.

1. Handling Images, Audios, Videos and PDF files is remaining for Notion connector.
2. Handling Images, Audios, Videos and PDF files (OCR / Text extraction / Multimodal parsing) is remaining for Email/Gmail connector (currently capturing metadata only).
3. PDF, Word (.docx), and Excel (.xlsx) parsing is COMPLETED and operational! Remaining for Dropbox / Drive: media files (audio/video) and image OCR.
4. For dropbox, in word docx, the tables are collected and printed at the end together, check that later.
5. In pdfs, docx, images arent handed as of now.
6. LangGraph Multi-Tool Execution: Currently, logical multi-tool planning runs sequentially inside `_tool_node()` via a `for` loop because local Qdrant/BM25 lookups take < 5ms. In the future when integrating remote HTTP APIs or high-latency network connectors, upgrade `_tool_node()` to use `ThreadPoolExecutor` or `asyncio.gather()` for true concurrent network I/O.
7. **TOON Formatting (Token-Oriented Object Notation)**: Pending implementation of compact, token-dense TOON representation for OKF concept bundles, global catalog index manifests (`global_index.md`), and retrieved evidence chunks. This will compress structural metadata (breadcrumbs, timestamps, tags, links) into minimal token footprints, preserving LLM context budgets and lowering inference latency on local 8B models.
8. **Explicit Query Scope Modifiers & Directives (`@enterprise`, `@docs`, `@general`, `@llm`, `@web`)**: Pending implementation of user-controlled prefix commands to explicitly control retrieval routing:
   - `@enterprise` / `@docs`: Forces enterprise retrieval pipeline (`catalog_discovery`, `hybrid_search`, `resource_lookup`, `github_entity_search`).
   - `@general` / `@llm`: Bypasses all enterprise retrieval tools and answers directly from LLM base knowledge / conversation history.
   - `@web`: Targets external internet / web documentation search (when external web search tool is enabled).
   - `@github`, `@jira`, `@notion`, `@dropbox`, `@gmail`, `@confluence`: Scopes search strictly to a specific connector platform.
   - *Detailed design and architecture guide authored in [`docs/query_scope_modifiers.md`](file:///Users/ompatil/Desktop/Enterprise-Knowledge-Agent/docs/query_scope_modifiers.md).*
