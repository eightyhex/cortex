# Cortex — Local-First AI-Native Second Brain

A knowledge management system that bridges your Obsidian vault with Claude via MCP. Capture notes, search intelligently, and manage your knowledge graph with zero cloud dependencies.

## 🎯 Vision

Cortex transforms your Obsidian vault into a queryable, intelligent knowledge base. Seamlessly capture thoughts, maintain relationships between notes, and retrieve information exactly when you need it—all powered by Claude, all local.

**Key idea:** Your vault is the single source of truth. Claude queries it via MCP tools. Three search systems (lexical, semantic, graph-based) work together to find what matters. Full lifecycle management: create, edit, archive, supersede.

## Quick Start

### 1. Install

**Option A — Install as a tool (recommended for end users):**

```bash
# Requires uv (https://docs.astral.sh/uv/)
uv tool install git+https://github.com/your-org/cortex.git
```

**Option B — Clone the repo (for development):**

```bash
git clone https://github.com/your-org/cortex.git
cd cortex
uv sync
```

### 2. Configure

Create your config file. If you installed as a tool, create `settings.yaml` in `~/.config/cortex/`. If you cloned the repo, create it in the project root:

```bash
# From the repo:
cp settings.example.yaml settings.yaml
```

Edit `settings.yaml` and set `vault.path` to your Obsidian vault location. Don't have a vault yet? Copy the example:

```bash
cp -r vault.example/ ~/Documents/my-cortex-vault
# then set vault.path: ~/Documents/my-cortex-vault in settings.yaml
```

### 3. Install the MCP Server

The `cortex install` command does everything automatically — it starts a background HTTP server, registers it with Claude Code, and configures Claude Desktop:

```bash
# If installed as a tool:
cortex install

# If running from the repo:
uv run cortex install
```

This creates a macOS LaunchAgent that:
- Starts the Cortex server automatically on login
- Restarts it if it crashes
- Runs a **single server process** shared by Claude Code and Claude Desktop

### 4. Restart Claude Apps & Build Index

Restart Claude Code and Claude Desktop to pick up the new MCP config, then tell Claude:

> "rebuild my cortex index"

This scans your vault and builds the search indexes. The embedding model (~270MB) downloads on first run.

### 5. Start Using It

See [Usage Guide](#-usage-guide) below for all available commands and examples.

### Managing the Server

```bash
cortex status     # check if the server is running
cortex restart    # restart (picks up code/config changes)
cortex uninstall  # remove LaunchAgent + MCP configs from Claude apps
```

### Updating Cortex

```bash
# If installed as a tool:
uv tool upgrade cortex
cortex restart

# If running from the repo:
git pull
cortex restart    # or: uv run cortex restart
```

### Enabling / Disabling Cortex

Cortex adds MCP tool definitions to your context window. To toggle it on and off without removing the config:

```bash
claude mcp disable cortex   # turn off (saves context)
claude mcp enable cortex    # turn back on
```

Restart Claude Code after toggling.

## 📖 Usage Guide

### Slash Commands

Cortex ships with Claude Code slash commands in `.claude/commands/`. These are available when working in this repo. To make them available globally, copy to your user config:

```bash
cp .claude/commands/cortex-*.md ~/.claude/commands/
```

| Command | What it does |
|---------|-------------|
| `/cortex-capture <thought>` | Capture a quick thought to your inbox |
| `/cortex-task <details>` | Add a task with optional due date and priority |
| `/cortex-link <url + description>` | Save a web link as a source note |
| `/cortex-note <content>` | Create any note type (concept, permanent, project, etc.) |
| `/cortex-search <query>` | Hybrid search across your vault (lexical + semantic + graph) |
| `/cortex-inbox` | Triage pending inbox items with categorization suggestions |
| `/cortex-review [weekly\|monthly]` | Generate a review summary of vault activity |
| `/cortex-stale` | Find notes that need review, archival, or categorization |
| `/cortex-stats` | Show vault statistics and system health |
| `/cortex-reindex` | Rebuild all search indexes from the vault |

### Natural Language (no slash commands)

You can also just talk to Claude naturally with the MCP enabled:

```
"save this thought: I should explore using LanceDB for the analytics pipeline"
"add a task: refactor auth middleware, due 2026-03-20, priority high"
"save this link: https://example.com/article — great intro to distributed consensus"
"search my vault for notes about authentication"
"process my inbox"
"give me a weekly review"
"find stale notes that need attention"
"what are my vault stats?"
```

### How Capture Works

All note captures go through a **draft-approve flow**:

1. You ask Claude to capture something
2. Claude creates a draft and shows you a preview
3. You approve, request edits, or reject
4. Only approved drafts are written to the vault

This prevents garbage from entering your knowledge base.

### MCP Tools Reference

These are the raw MCP tools that Claude calls under the hood:

| Tool | Description |
|------|-------------|
| `mcp_capture_thought` | Quick thought to inbox |
| `mcp_add_task` | Task with title, due date, priority |
| `mcp_save_link` | URL as a source note |
| `mcp_create_note` | Any note type (concept, permanent, project, etc.) |
| `approve_draft` | Approve a pending draft |
| `update_draft` | Edit a draft before approving |
| `reject_draft` | Discard a draft |
| `search_vault` | Hybrid search (lexical + semantic + graph) with optional date filtering (`created_after`, `created_before`) |
| `get_note` | Retrieve full note content by ID |
| `rebuild_index` | Rebuild all search indexes |
| `vault_stats` | Note counts, index sizes, last rebuild |
| `edit_note` | Start an edit on an existing note |
| `approve_edit` | Commit an edit after review |
| `archive_note` | Archive a note (deprioritized in search) |
| `unarchive_note` | Restore an archived note |
| `supersede_note` | Mark a note as replaced by a newer one |
| `detect_stale` | Find stale notes with suggested actions |
| `mcp_process_inbox` | List and categorize inbox items |
| `mcp_generate_review` | Weekly/monthly activity summary |
| `mcp_summarize_source` | Summarize a source note |
| `mcp_staleness_review` | Full staleness review with triage suggestions |
| `mcp_health_check` | System health check |

## 📚 Documentation

- **[Vision](docs/00-VISION.md)** — Original idea and core concept
- **[Product Requirements](docs/01-PRODUCT_REQUIREMENTS.md)** — Features, success metrics, session plan
- **[Architecture](docs/02-ARCHITECTURE.md)** — Complete technical design, Docker setup, implementation guide
- **[Critical Decisions](docs/03-CRITICAL_DECISIONS.md)** — Trade-offs and rationale

**New here?** Start with [docs/README.md](docs/README.md) for a guided tour.

## 🏗️ Project Structure

```
cortex/
├── README.md
├── pyproject.toml                    # Dependencies, build config
├── settings.example.yaml             # Config template — cp to settings.yaml
├── justfile                          # Task runner (just dev, just test, etc.)
├── .gitignore
├── .dockerignore
│
├── .claude/
│   └── commands/                     # Claude Code slash commands (/cortex-*)
│       ├── cortex-capture.md
│       ├── cortex-task.md
│       ├── cortex-link.md
│       ├── cortex-note.md
│       ├── cortex-search.md
│       ├── cortex-inbox.md
│       ├── cortex-review.md
│       ├── cortex-stale.md
│       ├── cortex-stats.md
│       └── cortex-reindex.md
│
├── docs/                             # Design documents
│   ├── README.md                     # Docs index + reading guide
│   ├── 00-VISION.md                  # Original concept
│   ├── 01-PRODUCT_REQUIREMENTS.md    # PRD (v0.3)
│   ├── 02-ARCHITECTURE.md            # TDD — complete design + Docker (v0.3)
│   └── 03-CRITICAL_DECISIONS.md      # Key trade-offs and rationale
│
├── src/cortex/                       # Main Python package
│   ├── __init__.py
│   ├── __main__.py                   # `python -m cortex` entry point
│   ├── cli.py                        # CLI: serve, install, uninstall, restart, status
│   ├── main.py                       # Backward-compat entry point (python -m cortex.main)
│   ├── vault/                        # Vault I/O, parsing, file watching
│   ├── index/                        # DuckDB FTS + LanceDB embeddings
│   ├── graph/                        # NetworkX knowledge graph
│   ├── query/                        # Hybrid search pipeline + RRF fusion
│   ├── capture/                      # Draft-based note capture
│   ├── lifecycle/                    # Edit, archive, supersede, staleness
│   ├── workflow/                     # Inbox, reviews, summarization
│   └── mcp/                          # FastMCP server + tool definitions
│
├── tests/                            # pytest test suite
│   ├── conftest.py                   # Shared fixtures (test vault, indexes)
│   ├── test_vault/
│   ├── test_index/
│   ├── test_graph/
│   ├── test_query/
│   ├── test_capture/
│   ├── test_lifecycle/
│   └── test_workflow/
│
├── evals/                            # Retrieval quality eval framework
│   ├── golden_dataset.json           # Annotated query → expected-result pairs
│   ├── harness.py                    # Eval runner
│   ├── metrics.py                    # MRR@10, Precision@5, NDCG@10
│   └── snapshots/                    # Versioned score history
│
├── vault.example/                    # Reference vault structure + templates
│   ├── README.md                     # How to set up your own vault
│   ├── 00-inbox/, 01-daily/, ...     # Folder structure
│   └── _templates/                   # Note templates (inbox, task, source, ...)
│
└── scripts/
    ├── docker-entrypoint.sh          # Docker first-run init + server startup
    └── dev-loop.sh                   # Task-driven development loop

# Not in repo (git-ignored):
# settings.yaml       ← your machine-specific config (copied from settings.example.yaml)
# vault/              ← your actual Obsidian vault (managed separately)
# data/               ← derived indexes, embeddings, graph (always rebuildable)
```

## 🔧 Technology Stack

| Component | Technology | Why? |
|---|---|---|
| **Language** | Python 3.14+ | Rich ML/NLP ecosystem, fast prototyping |
| **MCP Server** | FastMCP 3.x | Type-hint schemas, streamable-http transport, multi-client |
| **Full-text Search** | DuckDB FTS | BM25 scoring, embedded, SQL-friendly |
| **Vector Store** | LanceDB | Embedded, columnar, incremental updates |
| **Embeddings** | sentence-transformers (`nomic-embed-text`) | Local, CPU-friendly, 768-dim vectors |
| **Knowledge Graph** | NetworkX + GraphML | Relationship-aware queries, rebuildable |
| **Markdown Parsing** | python-frontmatter + mistune | YAML metadata + AST |
| **File Watching** | watchdog | Cross-platform, incremental indexing |
| **Containerization** | Docker + Docker Compose | Zero-config deployment, reproducible |
| **Project Management** | uv | Fast, deterministic |
| **Testing** | pytest + pytest-asyncio | Async-aware, fixtures |

## 🎯 Success Metrics

- **Retrieval relevance:** Top-5 results contain the right note ≥80% of time
- **Capture-to-indexed:** <5 seconds (file watcher + incremental index)
- **Query latency:** <3 seconds (hybrid: lexical + semantic + graph)
- **Eval score:** MRR@10 ≥0.7, Precision@5 ≥0.6, NDCG@10 ≥0.65
- **Vault size support:** 1,000+ notes without degradation
- **Docker:** `docker compose up` → working system in <5 minutes

## 🚀 Implementation Roadmap

14 sessions across ~8 weeks:

1. **Project Scaffolding & Docker Setup** — pyproject.toml, Dockerfile, docker-compose.yml, vault structure
2. **Markdown Parser** — Frontmatter extraction, link/tag parsing
3. **Capture & Review-Before-Create** — Draft system, all capture types
4. **Lexical Index** — DuckDB FTS with BM25
5. **Semantic Index** — LanceDB + sentence-transformers
6. **Hybrid Search** — RRF fusion + context assembly
7. **FastMCP Server** — Tool definitions, MCP integration
8. **Knowledge Graph** — NetworkX + GraphML persistence
9. **Eval Framework** — Golden dataset, harness, metrics
10. **Heuristic Reranking** — Score tuning, quality improvement
11. **Lifecycle Management** — Edit, archive, supersede, staleness
12. **Workflows** — Inbox processing, reviews, summarization
13. **File Watching** — Incremental updates, conflict resolution
14. **Polish & Docker Hardening** — Docs, health checks, troubleshooting

**See [docs/02-ARCHITECTURE.md § 7](docs/02-ARCHITECTURE.md) for detailed session plans with deliverables and exit criteria.**

## 💡 Key Design Decisions

### Why Three Search Systems?

- **Lexical (DuckDB FTS):** Exact term matching, Boolean queries
- **Semantic (LanceDB):** Meaning-based similarity
- **Graph (NetworkX):** Relationship navigation

All three run in parallel. RRF merges results. No routing/classification needed.

### Why Review-Before-Create?

All note captures (via MCP tools) produce a draft preview first. Users approve, edit, or reject before anything hits the vault. Prevents accidentally capturing garbage.

### Why Docker?

Users should go from `git clone` to `docker compose up` to working system. No Python install, no manual dependency management, no model downloads. Docker caches the embedding model in a separate layer.

### Why Streamable HTTP?

Cortex runs as a single background server process using FastMCP's `streamable-http` transport. This allows multiple clients (Claude Code, Claude Desktop, future web UIs) to connect to the same server simultaneously, avoiding DuckDB lock conflicts from multiple stdio processes. The server auto-starts on login via a macOS LaunchAgent and restarts if it crashes.

**Claude Code** connects directly via HTTP. **Claude Desktop** doesn't support HTTP transport natively, so `cortex install` configures it to use [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) as a lightweight stdio-to-HTTP bridge. This means Claude Desktop requires Node.js (`npx`) to be available on the system. Both clients share the same single server process — no duplicate instances.

---

## 🧪 Development

```bash
uv sync                       # install dependencies
uv run pytest                  # run all tests
uv run pytest evals/ -v        # run eval harness (retrieval quality)

# Server management (dev mode — runs from source)
uv run cortex install          # install LaunchAgent + configure Claude apps
uv run cortex restart          # restart after code changes
uv run cortex status           # check if running
uv run cortex uninstall        # remove LaunchAgent + configs

# Run server in foreground (for debugging)
uv run cortex serve            # HTTP on port 8757
uv run cortex stdio            # stdio mode (single client)
```

## 📋 Getting Started for Contributors

1. **Read the docs** (start with [docs/README.md](docs/README.md))
2. **Pick a session** from the implementation roadmap
3. **Follow the deliverables** listed in [docs/02-ARCHITECTURE.md § 7](docs/02-ARCHITECTURE.md)
4. **Write tests first** (TDD approach)
5. **Run evals** to validate retrieval quality
6. **Submit a PR** with clear description of what session you completed

---

## 📄 License

[Add your license here — MIT, Apache-2.0, etc.]

---

## 🙋 Questions?

- **Architecture questions?** See [docs/02-ARCHITECTURE.md](docs/02-ARCHITECTURE.md)
- **Why a specific tech choice?** See [docs/03-CRITICAL_DECISIONS.md](docs/03-CRITICAL_DECISIONS.md)
- **What's the next task?** Check the [implementation roadmap](#-implementation-roadmap)

---

**Last updated:** 2026-03-15 | **Version:** 1.0 | **Status:** Complete
