"""Context assembler — formats retrieval results into structured context for Claude."""

from __future__ import annotations

from cortex.query.fusion import FusedResult
from cortex.vault.parser import Note


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


class ContextAssembler:
    """Formats fused retrieval results into a structured context block for Claude."""

    def assemble(
        self,
        results: list[FusedResult],
        query: str,
        max_tokens: int = 4000,
        notes: dict[str, Note] | None = None,
    ) -> str:
        """Assemble results into a structured context string.

        Args:
            results: Fused search results to format.
            query: The original search query.
            max_tokens: Approximate token budget for the output.
            notes: Optional mapping of note_id -> Note for extra metadata
                (tags, links, created date, supersession info).

        Returns:
            Formatted context string with header and per-result blocks.
        """
        if not results:
            return f"## Query: {query}\n## Retrieved 0 results\n\nNo results found."

        notes = notes or {}

        # Determine retrieval methods used across all results
        methods = sorted({m for r in results for m in r.matched_by})
        methods_str = ", ".join(methods)

        header = (
            f"## Query: {query}\n"
            f"## Retrieved {len(results)} results via {methods_str}\n"
        )
        header_tokens = _estimate_tokens(header)

        # Build result blocks, truncating excerpts to fit budget
        remaining_tokens = max_tokens - header_tokens
        blocks: list[str] = []

        for i, result in enumerate(results, 1):
            note = notes.get(result.note_id)

            # Build metadata line
            result_tags = getattr(result, "tags", None)
            if note and note.tags:
                tags_str = ", ".join(note.tags)
            elif result_tags:
                tags_str = ", ".join(result_tags)
            else:
                tags_str = "none"
            links_str = (
                ", ".join(link.target_title for link in note.links)
                if note and note.links
                else "none"
            )
            created_str = (
                note.created.strftime("%Y-%m-%d") if note else "unknown"
            )

            block_header = (
                f"\n### Result {i}: {result.title} "
                f"(score: {result.score:.4f}, via: {', '.join(result.matched_by)})\n"
            )

            # Supersession warning
            superseded_warning = ""
            if note and note.superseded_by:
                successor = notes.get(note.superseded_by)
                successor_title = successor.title if successor else "unknown"
                superseded_warning = (
                    f"\u26a0 This note was superseded by: "
                    f"{successor_title} (id: {note.superseded_by})\n"
                )

            metadata_line = (
                f"Tags: {tags_str} | Links: {links_str} | Created: {created_str}\n"
            )

            # Calculate how much room is left for the excerpt
            frame = block_header + superseded_warning + metadata_line
            frame_tokens = _estimate_tokens(frame)
            excerpt_budget = remaining_tokens - frame_tokens

            if excerpt_budget <= 0:
                # No room left — stop adding results
                break

            excerpt = result.snippet or ""
            excerpt_tokens = _estimate_tokens(excerpt)

            if excerpt_tokens > excerpt_budget:
                # Truncate excerpt to fit
                char_budget = excerpt_budget * 4
                excerpt = excerpt[: char_budget - 3] + "..."

            block = block_header + superseded_warning + excerpt + "\n" + metadata_line
            block_tokens = _estimate_tokens(block)
            remaining_tokens -= block_tokens
            blocks.append(block)

        return header + "".join(blocks)
