# Cortex — Local-First AI-Native Second Brain

A knowledge management system that bridges your Obsidian vault with Claude via MCP. Capture notes, search intelligently, and manage your knowledge graph with zero cloud dependencies.

## 🎯 Vision

Cortex transforms your Obsidian vault into a queryable, intelligent knowledge base. Seamlessly capture thoughts, maintain relationships between notes, and retrieve information exactly when you need it—all powered by Claude, all local.

**Key idea:** Your vault is the single source of truth. Claude queries it via MCP tools. Three search systems (lexical, semantic, graph-based) work together to find what matters. Full lifecycle management: create, edit, archive, supersede.

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/your-org/cortex.git
cd cortex

# 1. Configure your vault path
cp settings.example.yaml settings.yaml
# Edit settings.yaml: set vault.path to your Obsidian vault

# 2. Start the server
CORTEX_VAULT_PATH=~/Documents/my-vault docker compose up -d
```

### Bare-Metal (no Docker)

```bash
git clone https://github.com/your-org/cortex.git
cd cortex

# 1. Install dependencies (requires Python 3.11+ and uv)
uv sync

# 2. Configure your vault
cp settings.example.yaml settings.yaml
# Edit settings.yaml: set vault.path to your Obsidian vault

# 3. Start MCP server
uv run python -m cortex.main
```

### Configure Claude Code

Add the following to your Claude Code MCP settings (`~/.claude/settings.json` or project `.mcp.json`):

**Docker:**

```json
{
  "mcpServers": {
    "cortex": {
      "command": "docker",
      "args": ["compose", "-f", "/path/to/cortex/docker-compose.yml", "run", "--rm", "-i", "cortex"],
      "env": {
        "CORTEX_VAULT_PATH": "/absolute/path/to/your/vault"
      }
    }
  }
}
```

**Bare-metal (uv):**

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/cortex", "python", "-m", "cortex.main"],
      "env": {
        "CORTEX_VAULT_PATH": "/absolute/path/to/your/vault"
      }
    }
  }
}
```

After configuring, restart Claude Code. The Cortex tools (`capture_thought`, `search_vault`, `add_task`, etc.) will appear automatically.

### Setting Up Your Vault

Cortex works with any Obsidian vault. Point `settings.yaml` at yours:

```yaml
vault:
  path: ~/Documents/my-vault   # wherever your Obsidian vault lives
```

Don't have a vault yet? Copy the example structure:

```bash
cp -r vault.example/ ~/Documents/my-cortex-vault
# then set vault.path in settings.yaml
```

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
├── docs/                             # Design documents
│   ├── README.md                     # Docs index + reading guide
│   ├── 00-VISION.md                  # Original concept
│   ├── 01-PRODUCT_REQUIREMENTS.md    # PRD (v0.3)
│   ├── 02-ARCHITECTURE.md            # TDD — complete design + Docker (v0.3)
│   └── 03-CRITICAL_DECISIONS.md      # Key trade-offs and rationale
│
├── src/cortex/                       # Main Python package
│   ├── __init__.py
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
    └── docker-entrypoint.sh          # Docker first-run init + server startup

# Not in repo (git-ignored):
# settings.yaml       ← your machine-specific config (copied from settings.example.yaml)
# vault/              ← your actual Obsidian vault (managed separately)
# data/               ← derived indexes, embeddings, graph (always rebuildable)
```

## 🔧 Technology Stack

| Component | Technology | Why? |
|---|---|---|
| **Language** | Python 3.11+ | Rich ML/NLP ecosystem, fast prototyping |
| **MCP Server** | FastMCP 3.x | Type-hint schemas, stdio transport, no HTTP overhead |
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

### Why stdio MCP?

No HTTP server overhead. Claude Code spawns the MCP process directly. Simpler architecture, lower latency, easier debugging.

---

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
