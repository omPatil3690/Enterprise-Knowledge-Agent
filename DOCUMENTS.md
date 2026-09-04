# Enterprise Knowledge Agent - Official Documentation & Developer Portal Directory

This document consolidates all essential external links, API references, developer portals, and credential management URLs needed to develop, configure, and maintain the Enterprise Knowledge Agent across all data sources, LLM providers, and storage engines.

---

## 📬 1. Email Connectors (Gmail API & Google Workspace)

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Google Cloud Console** | Main project dashboard and management | [console.cloud.google.com](https://console.cloud.google.com/) |
| **Google API Library** | Enable Gmail API and Google Workspace APIs | [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library) |
| **Google Auth Platform** | Configure OAuth 2.0 Consent Screen, Branding, and Test Users | [console.cloud.google.com/auth/overview](https://console.cloud.google.com/auth/overview) |
| **Google Credentials Console** | Create Desktop OAuth 2.0 Client IDs and download `credentials.json` | [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) |
| **Gmail API Overview & Quickstart** | Official Python Gmail API Quickstart guide | [developers.google.com/gmail/api/quickstart/python](https://developers.google.com/gmail/api/quickstart/python) |
| **Gmail API REST Reference** | Endpoints for `users.messages.list` and `users.messages.get` | [developers.google.com/gmail/api/reference/rest/v1/users.messages](https://developers.google.com/gmail/api/reference/rest/v1/users.messages) |
| **Gmail OAuth Scopes** | Least-privilege OAuth scopes guide (`gmail.readonly`) | [developers.google.com/gmail/api/auth/scopes](https://developers.google.com/gmail/api/auth/scopes) |
| **Google Auth Python Docs** | Python library documentation for `google-auth` & `google-auth-oauthlib` | [google-auth.readthedocs.io](https://google-auth.readthedocs.io/) |

---

## 📝 2. Notion Connector

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Notion Developer Portal** | Create internal integrations and retrieve `NOTION_TOKEN` | [notion.so/profile/integrations](https://www.notion.so/profile/integrations) |
| **Notion Connections Manager** | Manage workspace internal connections & content access | [app.notion.com/developers/connections](https://app.notion.com/developers/connections) |
| **Notion API Documentation** | Official Notion Developer Documentation hub | [developers.notion.com](https://developers.notion.com/) |
| **Notion Search Endpoint Reference** | OpenAPI spec & guide for `POST /v1/search` | [developers.notion.com/reference/post-search](https://developers.notion.com/reference/post-search) |
| **Notion Block Objects Reference** | Semantic structure for headings, toggles, callouts, tables | [developers.notion.com/reference/block](https://developers.notion.com/reference/block) |
| **Notion Databases Query Reference** | API documentation for `POST /v1/databases/{id}/query` | [developers.notion.com/reference/post-database-query](https://developers.notion.com/reference/post-database-query) |
| **Notion API Versioning** | Release notes and breaking change guides across API versions | [developers.notion.com/reference/versioning](https://developers.notion.com/reference/versioning) |

---

## 📦 3. Dropbox Connector

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Dropbox Developer App Console** | Create Dropbox Apps, manage permissions, and view App Key/Secret | [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps) |
| **Dropbox OAuth 2.0 Guide** | Documentation on short-lived tokens and `token_access_type=offline` | [developers.dropbox.com/oauth-guide](https://developers.dropbox.com/oauth-guide) |
| **Dropbox Python SDK Docs** | Official Python SDK reference (`dropbox.Dropbox`, OAuth flows) | [dropbox-sdk-python.readthedocs.io](https://dropbox-sdk-python.readthedocs.io/) |
| **Dropbox API HTTP Reference** | Endpoints for `/files/list_folder`, `/files/download`, `/users/get_current_account` | [dropbox.com/developers/documentation/http/documentation](https://www.dropbox.com/developers/documentation/http/documentation) |
| **Dropbox API Explorer** | Interactive API testing tool for Dropbox endpoints | [dropbox.github.io/dropbox-api-v2-explorer](https://dropbox.github.io/dropbox-api-v2-explorer/) |

---

## 💼 4. Atlassian Connectors (Confluence & Jira)

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Atlassian Security Tokens** | Generate and manage API tokens for Confluence & Jira | [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| **Confluence Cloud REST API (v2)** | Official Confluence API documentation for pages & spaces | [developer.atlassian.com/cloud/confluence/rest/v2/intro](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/) |
| **Jira Cloud REST API (v3)** | Official Jira API documentation for issues, epics, & sprints | [developer.atlassian.com/cloud/jira/platform/rest/v3/intro](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/) |
| **Atlassian Document Format (ADF)** | Specification for parsing rich structured text in Jira & Confluence | [developer.atlassian.com/cloud/jira/platform/apis/document/structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/) |

---

## 🐙 5. Code & Collaboration Connectors (GitHub, Slack, Google Drive)

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **GitHub Token Settings** | Generate Personal Access Tokens (Classic or Fine-Grained) | [github.com/settings/tokens](https://github.com/settings/tokens) |
| **GitHub REST API Docs** | Endpoints for repositories, pull requests, issues, and commits | [docs.github.com/en/rest](https://docs.github.com/en/rest) |
| **Slack App Management** | Create Slack Apps, configure bot tokens, and subscribe to events | [api.slack.com/apps](https://api.slack.com/apps) |
| **Slack Bot Scopes** | Documentation for `channels:read`, `channels:history`, `chat:write` | [api.slack.com/scopes](https://api.slack.com/scopes) |
| **Google Drive API Python** | Quickstart and reference for reading Google Docs and Drive folders | [developers.google.com/drive/api/quickstart/python](https://developers.google.com/drive/api/quickstart/python) |

---

## 🤖 6. LLMs, Embedding Models & AI Providers

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Google AI Studio** | Generate Gemini API Keys (`GEMINI_API_KEY`) and test prompts | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| **Google GenAI Python SDK Docs** | Official SDK guides for `google-genai` and text-embedding-004 | [ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs) |
| **OpenAI Developer Platform** | Manage OpenAI API Keys (`OPENAI_API_KEY`) and usage | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **OpenAI Embeddings Guide** | Reference for `text-embedding-3-small` / `text-embedding-3-large` | [platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings) |
| **Anthropic Console** | Manage Claude API Keys (`ANTHROPIC_API_KEY`) | [console.anthropic.com](https://console.anthropic.com/) |

---

## 🗄️ 7. Vector & Graph Database Infrastructure

| Resource | Purpose | Official URL |
| :--- | :--- | :--- |
| **Qdrant Documentation** | Vector search engine documentation, filtering, and payload indexing | [qdrant.tech/documentation](https://qdrant.tech/documentation/) |
| **Qdrant Cloud Console** | Managed Qdrant cluster provisioning and API key access | [cloud.qdrant.io](https://cloud.qdrant.io/) |
| **ChromaDB Documentation** | Lightweight embedded vector database documentation | [docs.trychroma.com](https://docs.trychroma.com/) |
| **Neo4j Aura Console** | Cloud-managed Neo4j Graph Database instances | [console.neo4j.io](https://console.neo4j.io/) |
| **Neo4j Cypher Manual** | Cypher Query Language reference for GraphRAG entity retrieval | [neo4j.com/docs/cypher-manual/current](https://neo4j.com/docs/cypher-manual/current/) |
