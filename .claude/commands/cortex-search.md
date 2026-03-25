---
description: Search your Cortex vault using hybrid retrieval
---

Use the `search_vault` tool to search the user's Cortex vault.

Query: $ARGUMENTS

If the user's query mentions a date or time range (e.g. "last Friday", "this week", "in March"), use the `created_after` and/or `created_before` parameters to filter by date. These accept ISO date strings like "2026-03-20".

Present the results clearly with titles, scores, matched-by sources, and snippets. If results reference specific notes the user might want to read in full, offer to retrieve them with `get_note`.
