# Product Requirements Document: Cortex — Local-First AI-Native Second Brain

**Version:** 0.3
**Date:** 2026-03-14
**Status:** Draft (updated per critical evaluation decisions)

---

## 1. Vision & Problem Statement

### The Problem

Knowledge workers accumulate information across dozens of sources — articles, repos, conversations, ideas, tasks — but have no unified system that lets them *capture fast* and *retrieve smart*. Existing tools force a choice: either manual organization (Obsidian, Notion) or AI-powered search (Mem, Rewind) with cloud lock-in.

### The Vision

**Cortex** is a local-first, AI-native second brain where:

- All knowledge lives in a plain-text Obsidian vault (portable, future-proof)
- A hybrid retrieval engine (lexical + semantic + graph) does the heavy reasoning
- Claude Code acts as the sole interface — you talk to your knowledge base in natural language
- Everything runs locally — no cloud dependencies, no API costs for core operations

### Core Principle

> Claude = orchestrator. The retrieval system = reasoning substrate.

Claude does not *search* the vault by reading raw markdown. The retrieval system handles discovery and ranking. Claude reads the *retrieved* content to perform generative tasks — synthesizing answers, summarizing sources, generating reviews, and editing notes. This separation ensures Claude never does brute-force search over the vault, while being honest that workflows like inbox processing, summarization, and review generation require Claude to reason over note content.

---

## 2. User Persona

**Primary user:** A solo knowledge worker / developer / researcher who:

- Already uses or is willing to use Obsidian as their note-taking tool
- Uses Claude Code as their daily coding and thinking assistant
- Wants to capture thoughts, links, and ideas without context-switching
- Wants to query their accumulated knowledge months later and get useful answers
- Values privacy and local-first tooling

---

## 3. User Experience

### 3.1 Capture Workflows

The user should be able to say things like:

| Command | What Happens |
|---|---|
| "Capture this thought: distributed caching might solve our latency issue" | Generates a draft note → shows preview → user approves/edits → saves to `inbox/` |
| "Add a task for tomorrow: review the PR for auth refactor" | Generates a draft task → shows preview → user approves/edits → saves to `02-tasks/` |
| "Save this repo: https://github.com/..." | Claude extracts URL metadata (title, description) → generates a draft source note → shows preview → user approves/edits → saves |
| "Save this article: https://..." | Claude extracts URL metadata (title, description, key points) → generates a draft source note → shows preview → user approves/edits → saves |
| "Start a concept note on vector databases" | Generates a draft concept note → shows preview → user approves/edits → saves |
| "Create a project note for Second Brain v2" | Generates a draft project note → shows preview → user approves/edits → saves |

### 3.1.1 Review-Before-Create Flow

**Every note creation must go through a preview-and-approve step before being written to the vault.** This is a core UX principle — the user always has the final say on what enters their knowledge base.

The flow works as follows:

1. **Draft:** The capture command generates the full note (frontmatter + body) as a draft in memory. Nothing is written to disk yet.
2. **Preview:** Claude presents the draft to the user, showing the title, tags, folder destination, and body content. The preview should be clearly formatted so the user can scan it quickly.
3. **User decision:**
   - **Approve** — the note is saved to the vault and indexed as-is.
   - **Edit** — the user provides changes (e.g., "change the tags to #python #architecture" or "add a section about trade-offs"). Claude regenerates the draft with the edits and shows a new preview.
   - **Reject** — the note is discarded. Nothing is saved.
4. **Save & Index:** Only after explicit approval is the note written to disk, indexed in DuckDB/LanceDB, and added to the knowledge graph.

This flow applies to all note types: inbox, task, source, concept, permanent, project, and review. The only exception is internal system operations (e.g., automated index metadata updates) that don't create user-facing notes.

### 3.2 Note Lifecycle Workflows

Notes are living documents. The system must support the full lifecycle: create → edit → supersede → archive. Without this, retrieval quality degrades over time as outdated notes compete with current ones.

| Command | What Happens |
|---|---|
| "Update my note about caching — we switched to Memcached" | Finds note → shows current version → generates updated draft → user reviews diff → approves → re-indexes all stores |
| "Archive my old Redis notes" | Finds matching notes → shows list → user confirms → sets status to `archived` + `archived_date` → re-indexes with scoring penalty |
| "This supersedes my old caching strategy note" | Creates new note with `supersedes` link → old note gets `status: superseded` + `superseded_by` link → graph gets `SUPERSEDES` edge |
| "What's gotten stale in my vault?" | Runs staleness detection → surfaces notes with no inbound links, no recent references, and old modification dates → user triages each |

### 3.2.1 Edit-with-Review Flow

Editing an existing note follows the same review principle as creation — the user always sees and approves changes before they're committed.

1. **Find:** User describes which note to update. Claude calls `search_vault` and presents candidates. User confirms which note.
2. **Load:** The system loads the current note content.
3. **Draft edit:** Claude generates an updated `NoteDraft` with the requested changes. The draft includes a diff view (what changed) alongside the full updated note.
4. **Review:** User approves, requests further edits, or cancels.
5. **Commit & re-index:** On approval, the file is overwritten, `modified` timestamp is updated, and all three indexes (DuckDB, LanceDB, NetworkX) are refreshed for this note. The old embedding is replaced, not appended.

### 3.2.2 Supersession & Archival

When knowledge evolves, notes don't just get edited — sometimes a new note entirely replaces an old one. The system tracks this explicitly:

- **Supersession** creates a directed `SUPERSEDES` edge in the graph. The old note gets `status: superseded` and a `superseded_by: <new-note-id>` field. The new note gets `supersedes: <old-note-id>`. When the old note surfaces in search results, the context assembler annotates it: "⚠ Superseded by [newer note title]."
- **Archival** sets `status: archived` and `archived_date`. Archived notes receive a configurable scoring penalty in the query pipeline (default: 0.5x multiplier on fusion score). They're still findable but won't crowd out active notes.
- **Staleness detection** is a workflow that identifies candidates for archival using note-type-aware thresholds. A note is considered potentially stale based on its type: inbox/task notes after 30 days, source notes after 90 days, concept/permanent notes after 365 days. Additional signals include: no inbound links (orphan), low search frequency, and old modification date. Permanent notes can be marked `evergreen: true` to exempt them from staleness detection entirely. The user reviews and decides per-note.

### 3.3 Retrieval Workflows

| Command | What Happens |
|---|---|
| "What do I know about agent memory?" | Hybrid search → ranked results → synthesized answer with sources |
| "Show connections between GraphRAG and my retrieval notes" | Graph traversal → relationship map → narrative summary |
| "Find all notes related to the Cortex project" | Project-scoped graph query → aggregated results |
| "What did I capture last week about distributed systems?" | Time-filtered lexical + semantic search |
| "Generate my weekly review" | Aggregates daily notes, tasks, captures from the past 7 days |

### 3.4 Processing Workflows

| Command | What Happens |
|---|---|
| "Process my inbox" | Reviews inbox items, suggests promotions to permanent/concept/project notes |
| "Summarize this source" | Takes a source note and generates a structured summary |
| "Cluster recent concepts" | Identifies thematic clusters across recent notes |
| "Generate monthly review" | Broader aggregation with trend analysis |

---

## 4. Feature Requirements (Phased)

### Phase 1 — Foundation (MVP)

**Goal:** Basic capture and retrieval works end-to-end through Claude Code.

| ID | Feature | Priority |
|---|---|---|
| F1.1 | Obsidian vault with defined folder structure, templates, and frontmatter schema | Must |
| F1.2 | Capture commands: thought, task, link, note | Must |
| F1.2a | Review-before-create flow: all note creation goes through draft → preview → approve/edit/reject | Must |
| F1.3 | Lexical search (full-text index over vault) | Must |
| F1.4 | Semantic search (local embeddings + vector store) | Must |
| F1.5 | Basic query pipeline (lexical + semantic fusion) | Must |
| F1.6 | Claude Code interface (MCP server or CLI — see §6) | Must |
| F1.7 | Vault indexing on startup and on file change | Must |
| F1.8 | Edit-with-review flow: find note → generate updated draft with diff → approve → re-index all stores | Must |

### Phase 2 — Graph & Intelligence

**Goal:** Relationship-aware retrieval and automated workflows.

| ID | Feature | Priority |
|---|---|---|
| F2.1 | Knowledge graph built from vault links and metadata | Must |
| F2.2 | Graph-aware retrieval (neighbor expansion, multi-hop) | Must |
| F2.3 | Heuristic reranking (recency, note type, link density, status). Cross-encoder deferred — add only if eval shows heuristic doesn't meet MRR@10 ≥ 0.7 | Should |
| F2.4 | Inbox processing workflow | Must |
| F2.5 | Weekly review generation | Should |
| F2.6 | Source summarization | Should |
| F2.7 | Supersession tracking: SUPERSEDES edge, `superseded_by` frontmatter, context annotation | Must |
| F2.8 | Archival flow: status change, scoring penalty in query pipeline, `archived_date` tracking | Must |
| F2.9 | Staleness detection workflow: identify orphan/stale notes, surface for user triage | Should |
| F2.10 | Retrieval eval framework: golden dataset, automated scoring, regression detection | Must |

### Phase 3 — Refinement & Automation

**Goal:** Polish, performance, and advanced features.

| ID | Feature | Priority |
|---|---|---|
| F3.1 | Note promotion workflow (inbox → permanent/concept) | Should |
| F3.2 | Concept clustering | Could |
| F3.3 | Monthly review generation | Should |
| F3.4 | Query result explanations (why matched, which system, ranking info) | Should |
| F3.5 | File watcher for real-time index updates | Should |
| F3.6 | Performance optimization (index caching, incremental updates) | Should |

### Phase 4 — Ecosystem

**Goal:** Extensibility and community-readiness.

| ID | Feature | Priority |
|---|---|---|
| F4.1 | Plugin/extension architecture for custom workflows | Could |
| F4.2 | Configurable embedding model selection | Could |
| F4.3 | Export/backup utilities | Could |
| F4.4 | Dashboard / stats (vault health, coverage, orphan notes) | Could |

---

## 5. Data Model Summary

### 5.1 Note Types

| Type | Folder | Purpose |
|---|---|---|
| Inbox | `00-inbox/` | Quick captures, unsorted |
| Daily | `01-daily/` | Daily journal / log |
| Task | `02-tasks/` | Actionable items |
| Source | `10-sources/` | External references (articles, repos, links) |
| Concept | `20-concepts/` | Reusable ideas and mental models |
| Permanent | `30-permanent/` | Refined, long-lived notes |
| Project | `40-projects/` | Project-scoped collections |
| Review | `50-reviews/` | Weekly/monthly reviews |
| Template | `_templates/` | Note templates |

### 5.2 Frontmatter Schema (Common Fields)

```yaml
---
id: <uuid>
title: <string>
type: <inbox|daily|task|source|concept|permanent|project|review>
created: <ISO datetime>
modified: <ISO datetime>
tags: [<string>]
status: <draft|active|archived|superseded>
source_url: <string|null>
related: [<note-id>]
# Lifecycle fields
supersedes: <note-id|null>         # ID of older note this replaces
superseded_by: <note-id|null>      # ID of newer note that replaced this
archived_date: <ISO datetime|null> # When this note was archived
evergreen: <bool|null>             # If true, exempt from staleness detection (concept/permanent notes)
---
```

### 5.3 Graph Nodes & Edges

**Phase 1 nodes:** Note, Project

**Phase 1 edges:** LINKS_TO, BELONGS_TO_PROJECT, SUPERSEDES

**Future phases:** Additional node types (Concept, Topic, Person) and edge types (DERIVED_FROM, RELATED_TO, ABOUT_TOPIC, MENTIONS, CAPTURED_ON) will be added when the eval framework validates they improve retrieval quality.

---

## 6. Claude Code Interface

**Decision: MCP Server via FastMCP 3.x with stdio transport.**

- Claude Code connects via the Model Context Protocol over stdio (stdin/stdout)
- Tools appear natively in Claude's tool list (`search_vault`, `capture_thought`, etc.)
- FastMCP provides decorator-based tool registration, automatic schema generation from type hints, and built-in stdio transport
- `fastmcp install claude-code server.py` auto-configures Claude Code's MCP settings
- No HTTP server, no ports, no process management — Claude Code spawns the MCP server process directly
- If a web UI or CLI is needed later, FastMCP also supports SSE and streamable HTTP transports via a transport argument change
- Project managed with `uv` for dependency resolution and script execution
- **Docker deployment:** The MCP server runs inside a Docker container. Claude Code's MCP config points to `docker compose run --rm -i cortex` (or `docker run` with appropriate volume mounts) as the stdio command. This eliminates all local Python/dependency setup — users only need Docker installed.

---

## 7. Constraints & Assumptions

- **Local-first:** No cloud services required for core functionality. The MCP server never makes HTTP requests — Claude handles any web access (e.g., URL metadata extraction for link capture).
- **Local embeddings:** Using sentence-transformers with `nomic-embed-text` (768-dim, trained on diverse corpus including code and technical text)
- **No vendor lock-in:** All data in plain markdown, indexes are rebuildable
- **Single user:** No multi-user or auth needed
- **Obsidian-compatible:** The vault must remain a valid Obsidian vault at all times
- **Python 3.14+:** Primary implementation language
- **uv:** Project management, dependency resolution, and script execution
- **Docker:** The entire system is containerized for one-command setup. Docker Compose orchestrates the MCP server with volume mounts for the vault and data directories. No manual Python/dependency installation required for end users.
- **Git-backed vault:** The vault should be a git repository for version history and backup. Obsidian Git plugin recommended for auto-commit. Push to a private remote for offsite backup.

---

## 8. Success Metrics

- Capture-to-indexed latency: < 5 seconds
- Edit-to-reindexed latency: < 5 seconds (all three indexes refreshed)
- Query response time: < 3 seconds for typical queries
- Retrieval relevance: user subjectively finds the right notes in top-5 results 80%+ of the time
- Retrieval eval score: MRR@10 ≥ 0.7 on the golden dataset (see §9a)
- After editing a note, the old version must not appear in any search results within 5 seconds
- Superseded notes must rank below their replacement for the same query
- Vault remains fully functional in Obsidian at all times
- System can handle a vault of 1,000+ notes without degradation
- Docker build completes in < 5 minutes on a fresh machine
- `docker compose up` starts the MCP server and all dependencies with zero manual configuration
- First-run experience: clone repo → `docker compose up` → configure Claude Code MCP → working system

---

## 9. Task Breakdown for Multi-Session Development

This is the recommended order for tackling the project across multiple Claude Code / Cowork sessions. Each task is scoped to be completable in a single session.

### Session 1: Project Scaffolding, Vault Structure & Docker Setup
- Initialize Python project with `uv` (`uv init`, `pyproject.toml`, directory structure)
- Initialize vault as a git repository
- Define vault folder structure and create it
- Create all note templates (frontmatter + body)
- Write vault README
- Create `Dockerfile` (multi-stage build: dependencies → model download → runtime)
- Create `docker-compose.yml` with volume mounts for vault and data
- Create `.dockerignore` to exclude vault data, caches, and local configs
- Add `scripts/docker-entrypoint.sh` for first-run initialization (vault scaffolding, model warm-up)
- Document Claude Code MCP configuration for Docker-based stdio transport

### Session 2: Markdown Parser & Metadata Extractor
- Build frontmatter parser (YAML extraction)
- Build wikilink / markdown link extractor
- Build tag extractor
- Unit tests for all parsers

### Session 3: Capture Commands & Review-Before-Create Flow
- Implement file-persisted draft system (`data/drafts/{draft_id}.json`) with 24h auto-cleanup
- Implement review-before-create flow: draft → preview → approve/edit/reject → save
- Implement `capture_thought`, `add_task`, `save_link`, `create_note` — all using the draft flow
- File naming: `{date}-{type}-{short-hash}-{slug}.md`
- `save_link` accepts pre-extracted metadata from Claude (title, description, tags)
- Unit tests (including approve, edit, and reject paths)

### Session 4: Lexical Index
- Set up DuckDB full-text search (or Tantivy)
- Build indexer that reads vault → populates index
- Implement search query interface
- Unit tests

### Session 5: Embedding Pipeline & Vector Store
- Set up sentence-transformers with `nomic-embed-text` (768-dim)
- Set up LanceDB as vector store
- Build indexer: vault → semantic-boundary chunks (paragraph/sentence split, ~300 token target, 500 max) → embeddings → LanceDB
- Implement semantic search interface
- Unit tests

### Session 6: Hybrid Search Fusion
- Every query runs all retrievers in parallel (no router — always lexical + semantic + graph)
- Implement result fusion (RRF)
- Build context assembler (format results for Claude)
- Integration tests

### Session 7: MCP Server
- Set up FastMCP 3.x MCP server with stdio transport
- Expose capture tools (thought, task, link, note) with draft-based review flow
- Expose search tools (search, query)
- `fastmcp install claude-code` to configure Claude Code
- Test with Claude Code

### Session 8: Knowledge Graph
- Build knowledge graph using NetworkX with GraphML persistence (safe, human-readable)
- Phase 1 graph: Note nodes + Project nodes + LINKS_TO edges + BELONGS_TO_PROJECT edges
- Implement graph queries (neighbors, paths, clusters)
- Integrate graph results into hybrid search fusion

### Session 9: Retrieval Eval Framework
- Build golden dataset: 50+ annotated query → expected-results pairs
- Implement eval harness: runs queries, computes MRR@10, Precision@5, NDCG@10
- Implement index consistency checker (all three stores agree on vault state)
- Establish baseline scores before any tuning
- Store results as versioned JSON snapshots for regression tracking

### Session 10: Heuristic Reranking & Quality Tuning
- Implement heuristic reranking (boost by recency, note type, link density, status multipliers)
- Tune fusion weights and heuristic boost parameters using eval framework
- Cross-encoder reranking deferred — add only if eval shows heuristic doesn't meet MRR@10 ≥ 0.7
- Run eval, compare against Session 9 baseline — must improve or match

### Session 11: Note Lifecycle Management
- Implement edit-with-review flow: find → load → draft edit with diff → approve → re-index
- Implement archival flow: status change, `archived_date`, scoring penalty in query pipeline
- Implement supersession flow: `SUPERSEDES` edge, `superseded_by`/`supersedes` frontmatter, context annotation
- Implement staleness detection with note-type-aware thresholds (inbox/task=30d, source=90d, concept/permanent=365d) and `evergreen` exemption
- Add lifecycle-specific eval cases to golden dataset
- Run eval, verify no regression from Session 10

### Session 12: Workflows
- Implement inbox processing
- Implement weekly review generation
- Implement source summarization
- Implement staleness review workflow
- Integration tests

### Session 13: File Watching & Incremental Updates
- Set up file watcher (watchdog)
- Implement incremental index updates (including edit and archive cascades)
- Implement incremental graph updates
- Conflict resolution: Obsidian always wins — external changes re-index, stale drafts discarded
- Performance testing

### Session 14: Polish, Documentation & Docker Hardening
- Error handling and edge cases
- Configuration file (settings.yaml)
- Setup script / installation guide (using `uv` for development, Docker for production)
- User documentation (including git-based backup setup, Obsidian Git plugin recommendation)
- Docker documentation: quick-start guide, volume mount reference, GPU acceleration, troubleshooting
- Health check endpoint for Docker container monitoring
- Final eval run — must meet all success metrics (including Docker-based runs)

---

*End of PRD*
