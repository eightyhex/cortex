# Cortex Documentation

Design documents for Cortex — a local-first, AI-native second brain built on Obsidian, powered by FastMCP.

## Document Guide

### 00-VISION.md
**Original idea and inspiration.** Captures the core concept: a knowledge management system that bridges your Obsidian vault with Claude via MCP, enabling intelligent capture, search, and lifecycle management of notes.

### 01-PRODUCT_REQUIREMENTS.md
**The PRD (v0.3).** Defines what we're building:
- User-facing features (capture, search, lifecycle management)
- Success metrics (retrieval quality, latency targets)
- Implementation roadmap across 14 sessions
- Docker as the primary deployment mechanism
- Constraints and assumptions

**Read this if:** You want to understand what features to build and why.

### 02-ARCHITECTURE.md
**The TDD (v0.3).** Deep technical design:
- Architecture overview (MCP server, three storage backends, query pipeline)
- Technology stack (FastMCP, DuckDB, LanceDB, NetworkX, sentence-transformers)
- Component design (VaultManager, DraftManager, LifecycleManager, indexes, graph)
- Data flow diagrams (capture, edit, query flows)
- Complete Docker design (multi-stage Dockerfile, compose, entrypoint script)
- Session-by-session implementation guide with deliverables and exit criteria
- Testing strategy and eval framework
- Performance targets and risk mitigation

**Read this if:** You're implementing features or need to understand the system design.

### 03-CRITICAL_DECISIONS.md
**Critical evaluation and decision rationale.** Documents key trade-offs:
- Why streamable-http MCP transport (single server, multi-client)
- Why three indexes (DuckDB + LanceDB + NetworkX)
- Why sentence-transformers `nomic-embed-text` (not API-based embeddings)
- Why Docker as primary deployment
- Why review-before-create for note capture
- Retrieval quality tuning approach

**Read this if:** You want to understand the "why" behind architectural choices.

---

## Quick Links

- **PRD Success Metrics** (01-PRODUCT_REQUIREMENTS.md § 8) — Retrieval quality targets, latency SLOs
- **Technology Stack** (02-ARCHITECTURE.md § 2) — Complete tool choices with rationale
- **Docker Design** (02-ARCHITECTURE.md § 6a) — Multi-stage build, compose config, MCP integration
- **Session 1 Deliverables** (02-ARCHITECTURE.md § 7) — Project scaffolding, vault structure, Docker setup
- **Eval Framework** (02-ARCHITECTURE.md § 8a) — Golden dataset, harness, metrics, regression detection
- **Performance Targets** (02-ARCHITECTURE.md § 9) — Build time, cold/warm start, query latency
- **Risk & Mitigation** (02-ARCHITECTURE.md § 10) — Docker image size, file watcher behavior, index consistency

## Repo Notes

- **`settings.example.yaml`** — Config template. Copy to `settings.yaml` (gitignored) and customize with your vault path.
- **`vault.example/`** — Reference vault structure + note templates. Your actual vault lives outside the repo.
- **`vault/`** is gitignored — point `settings.yaml → vault.path` at your Obsidian vault wherever it lives.
- **`data/`** is gitignored — always rebuildable from the vault via `just rebuild-index`.
- **`.claude/commands/`** — Claude Code slash commands (`/cortex-capture`, `/cortex-search`, etc.). Copy to `~/.claude/commands/` for global availability. See the main [README](../README.md#-usage-guide) for the full usage guide.

---

## Version History

- **v0.3** (2026-03-14) — Added comprehensive Docker support across all sessions
- **v0.2** (2026-03-14) — Critical evaluation phase — finalized tech stack, architecture, session plan
- **v0.1** — Initial design phase

---

## For New Contributors

Start here:
1. Read **00-VISION.md** (5 min) — Understand the big picture
2. Read **01-PRODUCT_REQUIREMENTS.md § 1-3** (10 min) — Understand features
3. Read **02-ARCHITECTURE.md § 1-2** (10 min) — Understand the stack
4. Jump to the session you're implementing (02-ARCHITECTURE.md § 7)

---

*Last updated: 2026-03-14*
