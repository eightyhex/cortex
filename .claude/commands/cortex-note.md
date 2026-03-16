---
description: Create a note of any type (concept, permanent, project, etc.) in Cortex
---

Use the `mcp_create_note` tool to create a note in the user's Cortex vault.

User input: $ARGUMENTS

Determine the appropriate note_type from the input. Valid types: inbox, daily, task, source, concept, permanent, project, review. Default to "concept" if unclear. Suggest relevant tags. Show the draft preview and ask for approval before calling `approve_draft`.
