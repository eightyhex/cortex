"""Staleness review workflow — guided triage of stale notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cortex.lifecycle.staleness import StaleCandidate, detect_stale_notes

if TYPE_CHECKING:
    from cortex.config import LifecycleConfig
    from cortex.graph.manager import GraphManager
    from cortex.vault.manager import VaultManager


def staleness_review(
    vault: VaultManager,
    graph: GraphManager,
    config: LifecycleConfig,
) -> list[StaleCandidate]:
    """Run staleness detection and return candidates formatted for triage.

    Wraps detect_stale_notes with the standard review workflow interface.
    Returns candidates sorted by staleness_score descending (most stale first).

    Args:
        vault: VaultManager for reading notes.
        graph: GraphManager for orphan detection.
        config: LifecycleConfig with staleness thresholds.

    Returns:
        List of StaleCandidate with suggested actions for each stale note.
    """
    return detect_stale_notes(vault, graph, config)
