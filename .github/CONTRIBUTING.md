# Contributing to Cortex

Thanks for your interest in Cortex! This guide will help you get started.

## Project Overview

Cortex is a local-first, AI-native second brain that bridges Obsidian with Claude via MCP. We're building it across 14 sessions, each with clear deliverables and exit criteria.

**Read first:**
- [README.md](../README.md) — Project overview
- [docs/02-ARCHITECTURE.md](../docs/02-ARCHITECTURE.md) — Complete technical design

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/cortex.git
   cd cortex
   ```

2. **Install dependencies**
   ```bash
   just setup        # Uses uv + installs pre-commit hooks
   ```

3. **Run tests**
   ```bash
   just test         # Run pytest
   just test-cov     # Run pytest with coverage
   ```

4. **Start development**
   ```bash
   just dev          # Start MCP server
   ```

## Contributing a Session

Each of the 14 implementation sessions is a self-contained unit. To contribute:

### 1. Pick a Session

Check [docs/02-ARCHITECTURE.md § 7](../docs/02-ARCHITECTURE.md) for the session plan. Pick one that isn't already in progress.

Example:
- Session 1: Project Scaffolding & Docker Setup ✅ (design complete)
- Session 2: Markdown Parser & Metadata Extractor (ready for implementation)
- etc.

### 2. Understand the Deliverables

Each session lists:
- **Deliverables:** Exactly what you need to build
- **Key behaviors:** What the code should do
- **Exit criteria:** How to know you're done

Example (Session 2):
```
Deliverables:
- src/cortex/vault/parser.py — parse_note(path) -> Note
- src/cortex/vault/manager.py — basic VaultManager (read operations)
- tests/test_vault/test_parser.py — 10+ test cases

Exit criteria: All parser tests pass. Can parse a sample vault of 20 notes.
```

### 3. Test-Driven Development

- **Write tests first** using the key behaviors as a guide
- Implement code to make tests pass
- Check exit criteria

```bash
# Write tests in tests/test_vault/test_parser.py
# Then run
just test-cov
```

### 4. Follow Code Style

```bash
just fmt          # Format with black + ruff
just lint         # Check style
just type-check   # Run mypy
```

### 5. Run Evals (if applicable)

For retrieval-related sessions, run the eval suite:

```bash
just rebuild-index  # Build indexes from test vault
just eval          # Run eval harness
```

### 6. Commit & Create PR

```bash
git checkout -b session-N-description
# Make changes
git add .
git commit -m "Session N: <clear description>"
git push origin session-N-description
```

In your PR:
- Link the session you're implementing
- Reference the deliverables from [docs/02-ARCHITECTURE.md](../docs/02-ARCHITECTURE.md)
- Show that exit criteria are met
- Include test coverage if relevant

**Example PR:**
```
## Session 2: Markdown Parser & Metadata Extractor

Implements `VaultManager` and frontmatter/link parsing per TDD § 7.

### Deliverables
- ✅ src/cortex/vault/parser.py with parse_note()
- ✅ src/cortex/vault/manager.py with read operations
- ✅ 15+ test cases covering frontmatter, wikilinks, tags, edge cases

### Exit Criteria
- ✅ All tests pass (100% coverage)
- ✅ Parser handles empty files, missing frontmatter, YAML errors
- ✅ Successfully parses sample 30-note vault

### Testing
```bash
just test -k test_vault
```
```

## Architecture Overview

**Quick summary:**
- Three search systems (lexical FTS, semantic embeddings, knowledge graph) run in parallel
- FastMCP server exposes tools to Claude Code via stdio
- Review-before-create: all captures generate a draft preview first
- Full lifecycle management: create, edit, archive, supersede, staleness detection

For details, see [docs/02-ARCHITECTURE.md](../docs/02-ARCHITECTURE.md).

## Design Decisions

If you're curious **why** we chose certain tech:

- **Why DuckDB + LanceDB + NetworkX?** See [docs/03-CRITICAL_DECISIONS.md](../docs/03-CRITICAL_DECISIONS.md)
- **Why stdio MCP?** See [docs/02-ARCHITECTURE.md § 1](../docs/02-ARCHITECTURE.md)
- **Why Docker?** See [docs/02-ARCHITECTURE.md § 6a](../docs/02-ARCHITECTURE.md)

## Testing Strategy

| Level | Scope | Tools |
|---|---|---|
| Unit | Individual functions (parsers, indexes) | pytest |
| Integration | Multi-component flows (capture → index) | pytest + fixtures |
| Lifecycle | Edit/archive/supersede flows | pytest + assertions |
| Retrieval | Query quality and ranking | Custom eval harness |

### Test Fixtures

Tests use a reusable **test vault fixture** (50 notes across all types with known relationships). See `tests/conftest.py`.

### Eval Framework

Retrieval quality is gated by the **eval framework** (golden dataset + harness). Every change to retrieval/ranking/lifecycle must pass evals.

```bash
just eval          # Run full eval suite
```

## Common Tasks

```bash
# Format code
just fmt

# Run type checking
just type-check

# Run tests + coverage
just test-cov

# Rebuild indexes from vault
just rebuild-index

# Start the MCP server
just dev

# Docker (if you're implementing Docker features)
just docker-build
just docker-up
```

## Questions?

- **Architecture questions?** Read [docs/02-ARCHITECTURE.md](../docs/02-ARCHITECTURE.md)
- **What session should I work on?** Check [docs/02-ARCHITECTURE.md § 7](../docs/02-ARCHITECTURE.md) and [docs/README.md](../docs/README.md)
- **How do I know if my code is done?** Check the **Exit criteria** for your session
- **Is my PR ready?** It should have tests, pass linting, and meet exit criteria

---

**Welcome! We're excited to have you contribute.** 🎉
