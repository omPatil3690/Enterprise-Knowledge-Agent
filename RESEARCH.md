# Where Does MCP Fit?

This is where things get really interesting.

**MCP = Model Context Protocol.**

It is fundamentally different from OKF.

A useful distinction is:

|                            | **OKF**                         | **MCP**                                          |
| -------------------------- | ------------------------------- | ------------------------------------------------ |
| **What is it?**            | Knowledge representation format | Protocol                                         |
| **Main purpose**           | Represent knowledge             | Connect AI applications to external capabilities |
| **Basic unit**             | Knowledge bundle / concept      | Server / tool / resource / prompt                |
| **Typical representation** | Markdown + YAML                 | Protocol messages / JSON                         |
| **Think of it as**         | **“How knowledge is packaged”** | **“How an agent accesses capabilities”**         |
| **Runtime required?**      | No                              | Yes                                              |
| **Search engine?**         | No                              | No                                               |
| **Database?**              | No                              | No                                               |

The current MCP specification describes MCP as the protocol layer for connecting AI applications with external systems, with capabilities such as **tools, resources, and prompts**. The July 2026 specification also introduced a stateless protocol core and strengthened authorization.

So:

> **OKF describes knowledge. MCP exposes capabilities.**

---

# What OKF Actually Is

The simplest mental model is:

> **OKF is a portable, human-readable knowledge representation format — not a database, not RAG, and not an API protocol.**

An OKF knowledge bundle is essentially:

```text
knowledge-bundle/
│
├── index.md
├── log.md
│
├── projects/
│   ├── index.md
│   ├── project-alpha.md
│   └── project-beta.md
│
├── services/
│   ├── payment-service.md
│   └── auth-service.md
│
└── teams/
    └── backend-team.md
```

Each concept is a Markdown file containing:

**YAML frontmatter + Markdown body**

For example, conceptually:

```yaml
---
type: Service
title: Payment Service
description: Handles payment processing
resource: https://...
tags: [payments, backend]
---
```

followed by Markdown describing the service and linking it to other concepts.

The important part is that relationships can be expressed through links between concepts.

So:

```text
payment-service.md
        │
        │ owned by
        ▼
backend-team.md
```

can become traversable knowledge.

---

# Think About the Notion API Model

This is the first thing I want you to understand before implementation.

A Notion page is not simply:

```text
Page
└── content: "some huge string"
```

Instead, Notion's content is structured into **blocks**.

Conceptually:

```text
Page
│
├── Page metadata
│   ├── ID
│   ├── URL
│   ├── title
│   ├── created time
│   └── last edited time
│
└── Blocks
    ├── paragraph
    ├── heading
    ├── paragraph
    ├── bulleted list
    ├── code
    ├── image
    └── ...
```

This distinction matters a lot for our eventual knowledge pipeline.

```text
Notion API JSON
        ↓
Extract page metadata
        ↓
Extract block content
        ↓
Flatten/normalize rich text
        ↓
Preserve document structure
        ↓
Store normalized JSON
```

The important point is:

> **Don't throw away information too aggressively yet.**

We want to extract the information useful for our agent while retaining enough metadata for retrieval, citations, permissions, and future graph construction.

---

# Notion Connector: Three Processing Layers

For the Notion connector, I suggest we think about processing in three layers.

## 1. Page-Level Information

From `/pages/{id}`, keep:

- `page_id`
- `title`
- `url`
- `created_time`
- `last_edited_time`
- `parent`
- `created_by`
- `last_edited_by`

The most important ones initially are:

- **`page_id`** → stable source identifier
- **`title`** → useful for retrieval/citations
- **`url`** → source citation
- **`last_edited_time`** → synchronization later
- **`parent`** → hierarchy/context

We don't need to carry the entire raw page JSON forward.

---

## 2. Block-Level Information

From `/blocks/{id}/children`, we want to transform blocks into meaningful **text + structure**.

For example:

```text
heading_1
"Architecture"

paragraph
"The backend uses FastAPI."

bulleted_list_item
"Neo4j is used for graph storage."
```

becomes something conceptually like:

```json
[
  {
    "type": "heading",
    "text": "Architecture"
  },
  {
    "type": "paragraph",
    "text": "The backend uses FastAPI."
  },
  {
    "type": "list_item",
    "text": "Neo4j is used for graph storage."
  }
]
```

We're essentially converting:

```text
Notion-specific JSON
        ↓
Useful structured knowledge
```

The reason we don't simply extract every `plain_text` value and concatenate it is that **structure carries meaning**.

For example:

```text
Architecture

FastAPI

PostgreSQL
```

is more useful than:

```text
Architecture FastAPI PostgreSQL
```

when we eventually chunk and retrieve it.

---

## 3. Preserve Source Information

Every extracted piece should still know where it came from.

Conceptually:

```json
{
  "page_id": "...",
  "page_title": "Project Architecture",
  "page_url": "...",
  "block_id": "...",
  "block_type": "paragraph",
  "text": "Backend uses FastAPI."
}
```

Why?

Later, if the agent says:

> The backend uses FastAPI.

we need to know:

- Which page?
- Which part of the page?
- What URL should I cite?

It also becomes important for updating/deleting knowledge when the Notion page changes.

---

# The Extraction Pipeline

Therefore, our extraction pipeline should be:

```text
Page API
    │
    ▼
Page metadata
    │
    ▼
Fetch blocks
    │
    ├── pagination ─────────┐
    │                       │
    ▼                       │
Block                       │
    │                       │
    ├── has_children?       │
    │       │               │
    │      yes              │
    │       ▼               │
    │   fetch children ─────┘
    │
    ▼
Extract useful content
    │
    ▼
Normalized Document
```

And this is another reason I would separate **retrieval from normalization**:

```text
retrieve_page()
retrieve_all_blocks()
        ↓
complete Notion data
        ↓
normalize()
        ↓
our Document model
```

That way, `normalize()` can assume we've already attempted to retrieve the complete page tree.

One more subtle point: we should also preserve the **hierarchy**, rather than flattening everything immediately. A heading, toggle, list, and nested block can carry contextual meaning.

We can flatten later during chunking if that's the best retrieval strategy.

---

# Do We Need a Database Model?

Yes, but **not necessarily a database model yet**.

For our project, I recommend having a small **data model for the normalized representation**. It gives us a clear contract between the Notion connector and everything downstream.

Think of three levels:

```text
Notion API JSON
      ↓
Notion-specific models
      ↓
Normalized Knowledge Document
      ↓
OKF
```

## 1. Do We Need Models for Raw Notion Responses?

**No, not initially.**

We can work with the API JSON dictionaries while learning the Notion structure.

For example:

```python
page = response.json()
blocks = response.json()
```

Creating models for every Notion API object would add unnecessary complexity right now.

---

## 2. Do We Need a Model for Our Normalized Document?

**Yes.**

Something conceptually like:

```python
class Document:
    source: str
    source_id: str
    title: str
    url: str
    created_at: ...
    updated_at: ...
    content: list[ContentBlock]
```

And:

```python
class ContentBlock:
    block_id: str
    type: str
    text: str
```

I would use **Pydantic** for these because we're building a Python/FastAPI system.

The benefit isn't just type checking. It establishes a contract:

```text
Notion Connector
       ↓
    Document
       ↓
Processing pipeline
```

The processing pipeline can trust that every `Document` has the expected structure regardless of where it came from.

Later:

```text
Notion ──┐
Slack ───┤
GitHub ──┤──→ Document
Drive ───┘
```

That's where the model becomes particularly valuable.

---

# One Important Distinction

I wouldn't make this model overly detailed yet.

Don't create:

```text
NotionPageModel
NotionParagraphModel
NotionHeadingModel
NotionCodeModel
NotionCalloutModel
...
```

unless we actually need them.

For our current stage, I'd keep it simple:

```text
Document
└── ContentBlock
```

This gives us a clean foundation without prematurely coupling the normalized knowledge model to every detail of the Notion API.

# Where Does MCP Fit?

This is where things get really interesting.

**MCP = Model Context Protocol.**

It is fundamentally different from OKF.

A useful distinction is:

|                            | **OKF**                         | **MCP**                                          |
| -------------------------- | ------------------------------- | ------------------------------------------------ |
| **What is it?**            | Knowledge representation format | Protocol                                         |
| **Main purpose**           | Represent knowledge             | Connect AI applications to external capabilities |
| **Basic unit**             | Knowledge bundle / concept      | Server / tool / resource / prompt                |
| **Typical representation** | Markdown + YAML                 | Protocol messages / JSON                         |
| **Think of it as**         | **“How knowledge is packaged”** | **“How an agent accesses capabilities”**         |
| **Runtime required?**      | No                              | Yes                                              |
| **Search engine?**         | No                              | No                                               |
| **Database?**              | No                              | No                                               |

The current MCP specification describes MCP as the protocol layer for connecting AI applications with external systems, with capabilities such as **tools, resources, and prompts**. The July 2026 specification also introduced a stateless protocol core and strengthened authorization.

So:

> **OKF describes knowledge. MCP exposes capabilities.**

---

# What OKF Actually Is

The simplest mental model is:

> **OKF is a portable, human-readable knowledge representation format — not a database, not RAG, and not an API protocol.**

An OKF knowledge bundle is essentially:

```text
knowledge-bundle/
│
├── index.md
├── log.md
│
├── projects/
│   ├── index.md
│   ├── project-alpha.md
│   └── project-beta.md
│
├── services/
│   ├── payment-service.md
│   └── auth-service.md
│
└── teams/
    └── backend-team.md
```

Each concept is a Markdown file containing:

**YAML frontmatter + Markdown body**

For example, conceptually:

```yaml
---
type: Service
title: Payment Service
description: Handles payment processing
resource: https://...
tags: [payments, backend]
---
```

followed by Markdown describing the service and linking it to other concepts.

The important part is that relationships can be expressed through links between concepts.

So:

```text
payment-service.md
        │
        │ owned by
        ▼
backend-team.md
```

can become traversable knowledge.

---

# Think About the Notion API Model

This is the first thing I want you to understand before implementation.

A Notion page is not simply:

```text
Page
└── content: "some huge string"
```

Instead, Notion's content is structured into **blocks**.

Conceptually:

```text
Page
│
├── Page metadata
│   ├── ID
│   ├── URL
│   ├── title
│   ├── created time
│   └── last edited time
│
└── Blocks
    ├── paragraph
    ├── heading
    ├── paragraph
    ├── bulleted list
    ├── code
    ├── image
    └── ...
```

This distinction matters a lot for our eventual knowledge pipeline.

```text
Notion API JSON
        ↓
Extract page metadata
        ↓
Extract block content
        ↓
Flatten/normalize rich text
        ↓
Preserve document structure
        ↓
Store normalized JSON
```

The important point is:

> **Don't throw away information too aggressively yet.**

We want to extract the information useful for our agent while retaining enough metadata for retrieval, citations, permissions, and future graph construction.

---

# Notion Connector: Three Processing Layers

For the Notion connector, I suggest we think about processing in three layers.

## 1. Page-Level Information

From `/pages/{id}`, keep:

- `page_id`
- `title`
- `url`
- `created_time`
- `last_edited_time`
- `parent`
- `created_by`
- `last_edited_by`

The most important ones initially are:

- **`page_id`** → stable source identifier
- **`title`** → useful for retrieval/citations
- **`url`** → source citation
- **`last_edited_time`** → synchronization later
- **`parent`** → hierarchy/context

We don't need to carry the entire raw page JSON forward.

---

## 2. Block-Level Information

From `/blocks/{id}/children`, we want to transform blocks into meaningful **text + structure**.

For example:

```text
heading_1
"Architecture"

paragraph
"The backend uses FastAPI."

bulleted_list_item
"Neo4j is used for graph storage."
```

becomes something conceptually like:

```json
[
  {
    "type": "heading",
    "text": "Architecture"
  },
  {
    "type": "paragraph",
    "text": "The backend uses FastAPI."
  },
  {
    "type": "list_item",
    "text": "Neo4j is used for graph storage."
  }
]
```

We're essentially converting:

```text
Notion-specific JSON
        ↓
Useful structured knowledge
```

The reason we don't simply extract every `plain_text` value and concatenate it is that **structure carries meaning**.

For example:

```text
Architecture

FastAPI

PostgreSQL
```

is more useful than:

```text
Architecture FastAPI PostgreSQL
```

when we eventually chunk and retrieve it.

---

## 3. Preserve Source Information

Every extracted piece should still know where it came from.

Conceptually:

```json
{
  "page_id": "...",
  "page_title": "Project Architecture",
  "page_url": "...",
  "block_id": "...",
  "block_type": "paragraph",
  "text": "Backend uses FastAPI."
}
```

Why?

Later, if the agent says:

> The backend uses FastAPI.

we need to know:

- Which page?
- Which part of the page?
- What URL should I cite?

It also becomes important for updating/deleting knowledge when the Notion page changes.

---

# The Extraction Pipeline

Therefore, our extraction pipeline should be:

```text
Page API
    │
    ▼
Page metadata
    │
    ▼
Fetch blocks
    │
    ├── pagination ─────────┐
    │                       │
    ▼                       │
Block                       │
    │                       │
    ├── has_children?       │
    │       │               │
    │      yes              │
    │       ▼               │
    │   fetch children ─────┘
    │
    ▼
Extract useful content
    │
    ▼
Normalized Document
```

And this is another reason I would separate **retrieval from normalization**:

```text
retrieve_page()
retrieve_all_blocks()
        ↓
complete Notion data
        ↓
normalize()
        ↓
our Document model
```

That way, `normalize()` can assume we've already attempted to retrieve the complete page tree.

One more subtle point: we should also preserve the **hierarchy**, rather than flattening everything immediately. A heading, toggle, list, and nested block can carry contextual meaning.

We can flatten later during chunking if that's the best retrieval strategy.

---

# Do We Need a Database Model?

Yes, but **not necessarily a database model yet**.

For our project, I recommend having a small **data model for the normalized representation**. It gives us a clear contract between the Notion connector and everything downstream.

Think of three levels:

```text
Notion API JSON
      ↓
Notion-specific models
      ↓
Normalized Knowledge Document
      ↓
OKF
```

## 1. Do We Need Models for Raw Notion Responses?

**No, not initially.**

We can work with the API JSON dictionaries while learning the Notion structure.

For example:

```python
page = response.json()
blocks = response.json()
```

Creating models for every Notion API object would add unnecessary complexity right now.

---

## 2. Do We Need a Model for Our Normalized Document?

**Yes.**

Something conceptually like:

```python
class Document:
    source: str
    source_id: str
    title: str
    url: str
    created_at: ...
    updated_at: ...
    content: list[ContentBlock]
```

And:

```python
class ContentBlock:
    block_id: str
    type: str
    text: str
```

I would use **Pydantic** for these because we're building a Python/FastAPI system.

The benefit isn't just type checking. It establishes a contract:

```text
Notion Connector
       ↓
    Document
       ↓
Processing pipeline
```

The processing pipeline can trust that every `Document` has the expected structure regardless of where it came from.

Later:

```text
Notion ──┐
Slack ───┤
GitHub ──┤──→ Document
Drive ───┘
```

That's where the model becomes particularly valuable.

---

# One Important Distinction

I wouldn't make this model overly detailed yet.

Don't create:

```text
NotionPageModel
NotionParagraphModel
NotionHeadingModel
NotionCodeModel
NotionCalloutModel
...
```

unless we actually need them.

For our current stage, I'd keep it simple:

```text
Document
└── ContentBlock
```

This gives us a clean foundation without prematurely coupling the normalized knowledge model to every detail of the Notion API.

---

Exactly. One page ID is only our unit of processing, not the scope of the connector.

We ultimately need to synchronize the entire set of Notion pages that our integration is allowed to access.

The architecture becomes:

                    Notion Workspace
                          │
                          ▼
                  Discover accessible pages
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          Page A        Page B       Page C
             │            │            │
             ▼            ▼            ▼
          Extract      Extract      Extract
             │            │            │
             └────────────┼────────────┘
                          ▼
                    Normalize
                          ▼
                    Knowledge Store

The important part: synchronization

We don't want to repeatedly process every page.

We need to distinguish:

NEW
MODIFIED
UNCHANGED

and eventually:

DELETED / NO LONGER ACCESSIBLE

For each page, we already get useful information from Notion such as:

page_id
last_edited_time

So we can maintain something like:

Our metadata store

## page_id last_synced_at source_updated_at

A 10:00 09:55
B 10:02 10:02
C 10:03 09:40

When synchronization runs:

Notion
│
▼
Discover pages
│
▼
Compare page metadata
│
├── New → process
├── Modified → process again
└── Unchanged → skip

For example:

Notion says:

Page A → last edited = 10:30
Our store → last processed = 10:00

10:30 > 10:00
↓
Re-process Page A

But:

Page B → last edited = 10:00
Our store → last processed = 10:00

same
↓
skip
One important architectural decision

We should not overwrite everything blindly when a page changes.

The lifecycle should eventually be:

Notion Page
↓
Retrieve latest version
↓
Parse
↓
Normalize
↓
Replace/update old representation
↓
Re-index

Because if the content changed, the old:

chunks
embeddings
keyword index entries
graph relationships

may no longer be valid.

So eventually a modification triggers something like:

Page modified
│
▼
Re-extract
│
▼
Re-normalize
│
├── Update vector index
├── Update keyword index
└── Update graph
But don't implement synchronization yet

For our current stage, I would keep the problem separated:

Stage 1

Given page_id
↓
retrieve complete page
↓
parse
↓
normalize

Stage 2

Discover all accessible pages
↓
identify new/changed pages
↓
call Stage 1 for each

This is a very important design principle: the page processor should not care whether a page was discovered for the first time or because it changed. It simply receives a page ID and produces the latest representation.

Then the synchronization layer decides which page IDs need processing.

So yes, your understanding is correct: the final connector is a synchronization system, not just a single-page API client. The single-page flow we're building now is the core processing unit that the later sync mechanism will repeatedly invoke.

---
