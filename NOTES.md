# This markdown file is for maintaining personal notes.

1. Handling Images, Audios, Videos and PDF files is remaining for notion connector.
2. Handling Images, Audios, Videos and PDF files (OCR / Text extraction / Multimodal parsing) is remaining for email/Gmail connector (currently capturing metadata only).
3. **[FUTURE] Cross-Platform Unified Neo4j Graph** — Currently the GitHub graph is scoped to GitHub-only entities. When other connectors (Notion, Gmail, Slack, Dropbox) are mature, all connectors should write into the **same single Neo4j database** (`neo4j` default). Each node should carry a `platform` property and use a namespaced `node_id` (e.g. `github:file:...`, `notion:page:...`, `gmail:thread:...`) to prevent ID collisions. This enables cross-connector graph traversal queries like:
   - "Which Slack message discussed the Notion page that describes the auth service Alice modified on GitHub?"
   - "Which Gmail thread referenced the PR that closed this issue?"
   Separate databases per connector would make these queries **impossible** — Neo4j databases are fully isolated graphs. The unified single-database approach is the correct architecture for Graph RAG over multi-source enterprise knowledge.
