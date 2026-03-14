# Cortex Vault — Example Structure

This directory shows the folder structure and note templates for a Cortex vault.

## Setup

Your actual vault should live **outside** this repository — wherever you keep your Obsidian files.

```bash
# Option A: Use this example as your starting vault
cp -r vault.example/ ~/Documents/my-cortex-vault
# Then update settings.yaml:
#   vault.path: ~/Documents/my-cortex-vault

# Option B: Point Cortex at an existing Obsidian vault
# Update settings.yaml:
#   vault.path: ~/Documents/ObsidianVault
```

## Folder Structure

| Folder | Purpose | Note type |
|--------|---------|-----------|
| `00-inbox/` | Quick captures — unprocessed, anything goes | inbox |
| `01-daily/` | Daily notes — created automatically | daily |
| `02-tasks/` | Task notes with due dates and priorities | task |
| `10-sources/` | Bookmarks, articles, papers, links | source |
| `20-concepts/` | Extracted concepts and ideas | concept |
| `30-permanent/` | Atomic permanent notes — distilled knowledge | permanent |
| `40-projects/` | Project-specific notes and tracking | project |
| `50-reviews/` | Weekly and monthly review notes | review |
| `_templates/` | Note templates — do not put notes here | — |

## Templates

Templates live in `_templates/`. Each corresponds to a note type that Cortex can capture.
See individual files for the expected frontmatter schema.

Cortex's `capture_thought`, `add_task`, `save_link`, and `create_note` tools use these templates when generating draft notes.

## Vault Rules

- **Cortex is the only thing that writes frontmatter** — don't manually edit YAML fields Cortex manages (id, created, status, supersedes, etc.)
- **Obsidian always wins** — if you edit a note in Obsidian, Cortex's file watcher picks up the change and re-indexes it within 5 seconds
- **Wikilinks are first-class** — use `[[Note Title]]` syntax to create relationships; Cortex builds the knowledge graph from these

---

*Part of the [Cortex](https://github.com/your-org/cortex) project.*
