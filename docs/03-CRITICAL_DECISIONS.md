# Critical Evaluation & Decision Tracker: Cortex — Second Brain Project

**Reviewer perspective:** Principal engineer & power user
**Date:** 2026-03-14
**Documents reviewed:** idea.txt, PRD-second-brain.md, TDD-second-brain.md
**Status:** All 16 issues reviewed and decided. PRD/TDD updates pending.

---

## Overall Assessment

This is an ambitious, well-structured project with solid fundamentals. The PRD and TDD are significantly above average for a personal project — clear phasing, explicit success metrics, an eval framework, and lifecycle management that most second-brain projects never consider. That said, there are several areas where the design is overengineered for its context, underspecified in critical places, or making choices that will create friction during actual use.

**Verdict:** Strong foundation, but needs targeted simplification and a few critical design corrections before implementation begins.

---

## What's Done Well

**Retrieval eval framework (§8a/§9 TDD).** This is the single best decision in the entire design. Most personal knowledge systems never define "good retrieval" in measurable terms. The golden dataset with regression tracking will prevent the most common failure mode: tuning one thing and silently breaking another. The lifecycle-specific eval cases (supersession correctness, edit consistency) are particularly thoughtful.

**Review-before-create flow.** Making every note pass through a draft → preview → approve cycle is the right call. It respects user agency and prevents the "AI stuffed garbage into my vault" problem that kills trust in these systems. The two-step MCP interaction pattern (capture returns draft, separate approve call) is clean.

**Source of truth discipline.** Vault is canonical, all derived stores are rebuildable. This is the correct architecture for a local-first system. The explicit index consistency guarantee (write vault first, then indexes, rebuild as recovery) is sound.

**Session-based implementation plan.** Breaking the project into 14 focused sessions with explicit exit criteria is practical and honest about the scope. This will actually get built, which is more than you can say for most designs of this complexity.

---

## Decision Log

### Critical Issues (Must Address)

#### 1. FastAPI MCP server is the wrong architecture

**Problem:** The TDD uses FastAPI as the MCP server backbone. Claude Code expects a stdio-based MCP server, not an HTTP server. FastAPI adds unnecessary process management, startup ordering, port conflicts, and health checks.

**Decision: Use FastMCP 3.x with stdio transport + uv for project management** ✅

- FastMCP provides decorator-based tool registration, automatic schema generation, and built-in stdio transport
- `fastmcp install claude-code server.py` auto-configures Claude Code
- `uv` for all dependency management and project tooling (replaces pip, virtualenv)
- No FastAPI, no uvicorn, no port config
- HTTP transport can be added later via FastMCP's SSE/streamable HTTP if a web UI is needed

**TDD changes required:**
- Tech stack: replace `FastAPI` + `uvicorn` with `FastMCP 3.x`; add `uv` as project manager
- Architecture diagram: "MCP Server (FastAPI)" → "MCP Server (FastMCP/stdio)"
- `settings.yaml`: remove `server.host` and `server.port`
- `main.py`: becomes FastMCP server entry point
- Session 7: focus on FastMCP tool registration, not HTTP routes
- `pyproject.toml`: managed by `uv`; replace `pip install` commands with `uv` equivalents
- `justfile`: commands use `uv run` instead of direct python

---

#### 2. NetworkX with pickle is a liability

**Problem:** Pickle deserialization can execute arbitrary code (RCE risk). Pickle is fragile across library version changes. Full graph serialized on every mutation.

**Decision: Keep NetworkX but serialize to GraphML instead of pickle** ✅

- NetworkX stays for its algorithm library (ego graphs, shortest paths, connected components, centrality)
- GraphML (XML) serialization replaces pickle — safe, human-readable, version-stable
- Backup before write (`graph.graphml.bak`)
- Still rebuildable from vault as fallback
- Full-load-on-startup is acceptable for <5K nodes (sub-second)

**TDD changes required:**
- Replace all `pickle` references with `GraphML` (`nx.read_graphml()` / `nx.write_graphml()`)
- File extension: `data/graph/graph.graphml` instead of `graph.pkl`
- Update risk table: remove pickle-related risks, note GraphML's human-readability as a benefit
- Update `GraphManager` code examples

---

#### 3. The query router is a premature abstraction

**Problem:** Six-category query classification is unspecified, most queries benefit from all retrieval systems, and "hybrid" is the catch-all anyway. The router adds complexity without clear benefit.

**Decision: Drop the query router for Phase 1. Always run all retrievers in parallel.** ✅

- Every query runs lexical + semantic + graph simultaneously
- RRF fusion merges all results
- No classification logic needed
- Router can be added in a future phase if eval data shows targeted routing improves specific categories

**TDD changes required:**
- Remove §4.5 query router section and the query type classification table
- Simplify `QueryPipeline` — always dispatches to all three systems
- Remove `router.py` from project structure
- Update Session 6 deliverables and exit criteria

---

#### 4. DuckDB FTS limitations

**Problem:** DuckDB's FTS extension is experimental with limited tokenization, doesn't natively index array columns, and may require full index rebuild on updates.

**Decision: Keep DuckDB FTS for Phase 1 with documented limitations and eval-driven migration path** ✅

- DuckDB FTS is good enough for <5K notes
- Tags stored as both `VARCHAR[]` (SQL filtering) and concatenated `VARCHAR` (FTS indexing)
- `LexicalIndex` abstraction ensures backend is swappable
- Migrate to Tantivy only if eval shows inadequate lexical recall
- Document FTS limitations explicitly in TDD

**TDD changes required:**
- Add a `tags_text VARCHAR` column alongside `tags VARCHAR[]`
- Document DuckDB FTS limitations and Tantivy migration path
- Add note about FTS index rebuild behavior

---

### Significant Design Concerns

#### 5. "Claude doesn't read raw markdown" principle is too absolute

**Problem:** Several workflows (inbox processing, summarization, reviews, editing) fundamentally require Claude to read note content. The retrieval system handles discovery, but Claude must reason over retrieved content.

**Decision: Reframe the principle** ✅

- New wording: "Claude does not search the vault by reading raw markdown. The retrieval system handles discovery and ranking. Claude reads retrieved content to perform generative tasks (summarization, review, editing)."
- PRD text update only, no code impact

**PRD changes required:**
- Update the core principle wording in the architecture section

---

#### 6. The draft system has a state management problem

**Problem:** In-memory `DraftManager` loses state on restart, doesn't handle concurrent drafts cleanly, and has no timeout mechanism.

**Decision: File-persisted drafts** ✅

- Drafts saved as JSON files in `data/drafts/{draft_id}.json`
- MCP server is stateless — reads draft from file on each operation
- Auto-cleanup: delete draft files older than 24 hours (on server startup or periodic sweep)
- Survives restarts, inspectable, supports concurrent drafts naturally

**TDD changes required:**
- Update `DraftManager` to use file persistence instead of `self._pending_drafts` dict
- Add `data/drafts/` to project structure
- Add cleanup logic (24h expiry) to server startup
- Remove "drafts discarded on restart" caveat

---

#### 7. Embedding model choice

**Problem:** `all-MiniLM-L6-v2` is general-purpose and may underperform on technical/code content and short texts.

**Decision: Switch to `nomic-embed-text` as the default** ✅

- 768-dim vectors, trained on diverse corpus including code and technical text
- Better performance on short queries
- Storage increase is negligible at vault scale (~3MB vs ~1.5MB for 1K notes)
- Still configurable — eval framework validates the choice

**TDD changes required:**
- Tech stack table: `all-MiniLM-L6-v2` → `nomic-embed-text`
- Update vector dimensions throughout (384 → 768)
- Update LanceDB schema
- Update `settings.yaml` defaults
- Update memory estimates

---

#### 8. Chunking strategy is underbaked

**Problem:** Fixed 256-token intervals with overlap cut paragraphs mid-thought. Note-level + chunk-level doubles vector count. Token counting is model-ambiguous.

**Decision: Semantic-boundary-aware splitting** ✅

- Split on paragraph boundaries first, then sentence boundaries
- Target ~300 tokens, max 500, using `nomic-embed-text` tokenizer
- No note-level embedding — boost note score in fusion if multiple chunks rank high
- No fixed overlap (semantic boundaries make it less necessary)

**TDD changes required:**
- Rewrite §4.3 chunking strategy section
- Update chunk size parameters in `settings.yaml`
- Remove note-level embedding from LanceDB schema description
- Add note-score boosting logic to fusion description

---

#### 9. Cross-encoder reranking may not be worth it

**Problem:** Adds ~100–200ms latency, ~80MB memory, trained on web queries not personal knowledge bases. Marginal benefit for a personal vault.

**Decision: Heuristic reranking for Phase 1, cross-encoder deferred** ✅

- Boost by recency, note type, link density, status multipliers
- Fast, interpretable, tunable via eval framework
- Add cross-encoder only if eval shows heuristic reranking doesn't meet MRR@10 ≥ 0.7
- Remove `cross-encoder/ms-marco-MiniLM-L-6-v2` from Phase 1 dependencies

**TDD changes required:**
- Session 10 scope: tune heuristic weights using eval, not cross-encoder integration
- Move cross-encoder to "future phase" section
- Remove reranker model from tech stack table (for Phase 1)
- Update `reranker.py` description to heuristic-based

---

#### 10. File naming collisions

**Problem:** `{date}-{type}-{slug}.md` can collide when multiple notes of the same type are captured on the same day.

**Decision: Add short UUID hash to filenames** ✅

- Format: `{date}-{type}-{short-hash}-{slug}.md`
- Short hash = first 4 chars of UUID hex (65K possibilities per day per type)
- Example: `2026-03-14-thought-a3f2-distributed-caching.md`

**TDD changes required:**
- Update file naming convention in vault manager and capture sections
- Update examples throughout

---

### Minor Issues & Suggestions

#### 11. No conflict handling for external Obsidian edits

**Problem:** File watcher doesn't specify behavior when Obsidian edits, deletes, or moves notes that may have pending drafts or active graph references.

**Decision: Obsidian always wins** ✅

- External changes are authoritative — re-index on detect
- Discard stale drafts if underlying note's `modified` timestamp changed since draft creation
- Deleted notes removed from all indexes
- Moved notes: update path in all indexes

**TDD changes required:**
- Add conflict resolution section to file watcher design (Session 13)
- Add draft staleness check (compare note modified timestamp to draft creation time)

---

#### 12. Graph node types are over-specified for Phase 1

**Problem:** 8 node types and 8 edge types require entity extraction logic before validating that graph retrieval helps.

**Decision: Phase 1 graph = Notes + Projects + LINKS_TO + BELONGS_TO_PROJECT** ✅

- Note nodes and LINKS_TO edges (from wikilinks)
- Project nodes and BELONGS_TO_PROJECT edges (from frontmatter — no extraction needed)
- Other entity types (concept, topic, person) deferred to Phase 2+
- Eval framework measures whether graph retrieval helps before adding complexity

**TDD changes required:**
- Simplify graph model section — show only Note, Project, LINKS_TO, BELONGS_TO_PROJECT
- Move other entity types to "future enhancements"
- Update Session 8 deliverables

---

#### 13. The "version" field on notes is noise

**Problem:** Incrementing a version number on each edit duplicates information already available from `modified` timestamps and git history.

**Decision: Drop the version field** ✅

- Use `modified` timestamp for recency
- Use git for full version history
- Less frontmatter clutter, less write overhead

**TDD changes required:**
- Remove `version: int` from `Note` dataclass
- Remove `version INTEGER` from DuckDB schema
- Remove version increment logic from lifecycle manager
- Update edit flow to not reference version numbers

---

#### 14. Staleness detection heuristics are too simple

**Problem:** Uniform 90-day threshold flags perfectly good reference notes (e.g., "CAP theorem" concept note untouched for a year).

**Decision: Note-type-aware staleness thresholds** ✅

- inbox/task: 30 days
- source: 90 days
- concept/permanent: 365 days
- Permanent notes can be marked "evergreen" to exempt from staleness entirely
- Search frequency reduces staleness score (frequently retrieved = probably still relevant)

**TDD changes required:**
- Update staleness detection heuristics with per-type thresholds
- Add `evergreen: bool` optional frontmatter field
- Add search frequency tracking (optional, for staleness scoring)

---

#### 15. How does "save this link" actually work?

**Problem:** URL metadata extraction requires HTTP requests, conflicting with "local-first, no API calls."

**Decision: Claude extracts URL metadata** ✅

- Claude uses its own browsing/web access to read the URL and extract title, description, key points
- Claude passes extracted metadata to the `save_link` tool as parameters
- The MCP server itself never makes HTTP requests — stays truly local
- If Claude can't access the URL, falls back to URL + user-provided description

**TDD/PRD changes required:**
- Document that `save_link` accepts `url`, `title`, `description`, `tags` as parameters
- Specify that Claude is responsible for metadata extraction, not the MCP server
- Add fallback behavior when URL is inaccessible

---

#### 16. Missing backup and recovery strategy

**Problem:** Vault is the single source of truth with no documented backup strategy.

**Decision: Git-based backup** ✅

- Vault is a git repo — document as a setup requirement
- Recommend Obsidian Git plugin for auto-commit
- Push to remote (GitHub/GitLab private repo) for offsite backup
- Cortex doesn't implement backup itself — well-documented user responsibility

**PRD/TDD changes required:**
- Add git initialization to setup instructions
- Recommend Obsidian Git plugin in prerequisites
- Add backup section to documentation plan (Session 14)

---

## Cross-Cutting Decision: Project Tooling

**Decision: Use `uv` for all project management** ✅

- `uv init`, `uv add`, `uv run` replace pip/virtualenv/poetry
- `pyproject.toml` managed by uv
- `justfile` commands use `uv run`
- Fast dependency resolution, lockfile support, Python version management

---

## Summary of All Decisions

| # | Issue | Original Recommendation | Decision | Status |
|---|-------|------------------------|----------|--------|
| 1 | FastAPI MCP server | Use mcp SDK with stdio | **FastMCP 3.x + stdio + uv** | ✅ Decided |
| 2 | NetworkX + pickle | SQLite for graph | **NetworkX + GraphML** | ✅ Decided |
| 3 | Query router | Drop for Phase 1 | **Dropped — always run all retrievers** | ✅ Decided |
| 4 | DuckDB FTS | Consider Tantivy | **Keep DuckDB FTS, eval-driven migration** | ✅ Decided |
| 5 | "Claude never reads markdown" | Reframe principle | **Reframed: doesn't search, but reads results** | ✅ Decided |
| 6 | Server-side draft state | Stateless (Claude holds draft) | **File-persisted drafts in data/drafts/** | ✅ Decided |
| 7 | Embedding model | Evaluate nomic-embed-text | **Switch to nomic-embed-text** | ✅ Decided |
| 8 | Chunking strategy | Semantic-boundary splitting | **Adopted — paragraph/sentence boundaries** | ✅ Decided |
| 9 | Cross-encoder reranking | Heuristic reranking first | **Adopted — cross-encoder deferred** | ✅ Decided |
| 10 | File naming collisions | Add short UUID hash | **Adopted — {date}-{type}-{hash}-{slug}.md** | ✅ Decided |
| 11 | Obsidian conflict handling | Obsidian wins | **Adopted — re-index, discard stale drafts** | ✅ Decided |
| 12 | Graph node types | Minimal graph | **Notes + Projects + 2 edge types** | ✅ Decided |
| 13 | Version field | Drop it | **Dropped — use modified + git** | ✅ Decided |
| 14 | Staleness heuristics | Type-aware thresholds | **Adopted — per-type thresholds + evergreen** | ✅ Decided |
| 15 | Link capture metadata | Claude extracts metadata | **Adopted — MCP server stays local** | ✅ Decided |
| 16 | Backup strategy | Git-based | **Adopted — document as requirement** | ✅ Decided |

---

## Next Steps

- [ ] Update PRD with decisions #1, #5, #15, #16
- [ ] Update TDD with decisions #1–14
- [ ] Review session plan for any sequencing changes based on decisions

---

*This evaluation focuses on decisions that will be painful to reverse later. The project has strong bones — the phasing is realistic, the eval framework is the right investment, and the local-first constraint is well-enforced. The main risk is overbuilding complexity in Phase 1 when a simpler system would let you iterate faster on what actually matters: retrieval quality.*
