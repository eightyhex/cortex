"""Staleness detection — identify stale notes using type-aware thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex.config import LifecycleConfig
    from cortex.graph.manager import GraphManager
    from cortex.vault.manager import VaultManager
    from cortex.vault.parser import Note


@dataclass
class StaleCandidate:
    """A note identified as potentially stale."""

    note: Note
    staleness_score: float
    reasons: list[str] = field(default_factory=list)
    suggested_action: str = "review"


def _days_since_modified(note: Note, now: datetime) -> float:
    """Return the number of days since the note was last modified."""
    modified = note.modified
    # Ensure timezone-aware comparison
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=timezone.utc)
    delta = now - modified
    return delta.total_seconds() / 86400


def _get_threshold(note_type: str, config: LifecycleConfig) -> int | None:
    """Return the staleness threshold in days for a note type, or None if exempt."""
    thresholds = config.staleness_thresholds
    mapping = {
        "inbox": thresholds.inbox,
        "task": thresholds.task,
        "source": thresholds.source,
        "concept": thresholds.concept,
        "permanent": thresholds.permanent,
    }
    return mapping.get(note_type)


def _has_inbound_links(graph: GraphManager, note_id: str) -> bool:
    """Check if a note has any inbound LINKS_TO edges."""
    if not graph.graph.has_node(note_id):
        return False
    for _src, _dst, data in graph.graph.in_edges(note_id, data=True):
        if data.get("rel_type") == "LINKS_TO":
            return True
    return False


def detect_stale_notes(
    vault: VaultManager,
    graph: GraphManager,
    config: LifecycleConfig,
) -> list[StaleCandidate]:
    """Identify stale notes using type-aware thresholds.

    Args:
        vault: VaultManager for reading notes.
        graph: GraphManager for orphan detection.
        config: LifecycleConfig with staleness thresholds.

    Returns:
        List of StaleCandidate sorted by staleness_score descending (most stale first).
    """
    now = datetime.now(timezone.utc)
    candidates: list[StaleCandidate] = []

    for note in vault.scan_vault():
        # Skip non-active notes
        if note.status in ("archived", "superseded"):
            continue

        # Skip evergreen notes
        if note.frontmatter.get("evergreen") is True:
            continue

        threshold = _get_threshold(note.note_type, config)
        if threshold is None:
            # Note types without thresholds (daily, project, review) are not checked
            continue

        days = _days_since_modified(note, now)
        reasons: list[str] = []
        score = 0.0

        # Age-based staleness
        if days > threshold:
            ratio = days / threshold
            score += ratio
            reasons.append(
                f"Not modified in {int(days)} days (threshold: {threshold}d)"
            )

        # Orphan detection
        is_orphan = not _has_inbound_links(graph, note.id)
        if is_orphan:
            score += 0.5
            reasons.append("Orphan: no inbound links from other notes")

        if not reasons:
            continue

        # Suggest action based on severity
        if score > 2.0:
            suggested_action = "archive"
        elif note.note_type == "inbox":
            suggested_action = "categorize"
        else:
            suggested_action = "review"

        candidates.append(
            StaleCandidate(
                note=note,
                staleness_score=score,
                reasons=reasons,
                suggested_action=suggested_action,
            )
        )

    # Sort by staleness score descending
    candidates.sort(key=lambda c: c.staleness_score, reverse=True)
    return candidates
