"""Review generation workflow — weekly/monthly summaries of vault activity."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from cortex.vault.manager import VaultManager
from cortex.vault.parser import Note


@dataclass
class ReviewDraft:
    """Aggregated review data for a time period."""

    period: str  # "weekly" or "monthly"
    start_date: date
    end_date: date
    total_notes: int
    counts_by_type: dict[str, int]
    new_captures: list[dict]
    completed_tasks: list[dict]
    active_projects: list[dict]
    key_themes: list[str]


def _in_period(note: Note, start: datetime, end: datetime) -> bool:
    """Check if a note was created within the given period."""
    created = note.created
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return start <= created <= end


def _extract_themes(notes: list[Note], max_themes: int = 10) -> list[str]:
    """Extract key themes from note tags."""
    tag_counts: Counter[str] = Counter()
    for note in notes:
        for tag in note.tags:
            tag_counts[tag] += 1
    return [tag for tag, _ in tag_counts.most_common(max_themes)]


def generate_review(
    vault: VaultManager,
    period: str = "weekly",
    target_date: date | None = None,
) -> ReviewDraft:
    """Generate a review summary for the given period.

    Args:
        vault: VaultManager instance to scan.
        period: "weekly" or "monthly".
        target_date: End date of the review period. Defaults to today.

    Returns:
        ReviewDraft with aggregated note data.
    """
    if target_date is None:
        target_date = date.today()

    if period == "monthly":
        # Go back ~30 days
        start_date = target_date - timedelta(days=30)
    else:
        # Default to weekly (7 days)
        start_date = target_date - timedelta(days=7)

    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    all_notes = vault.scan_vault()
    period_notes = [n for n in all_notes if _in_period(n, start_dt, end_dt)]

    counts_by_type = dict(Counter(n.note_type for n in period_notes))

    new_captures = [
        {"note_id": n.id, "title": n.title, "type": n.note_type, "created": n.created.isoformat()}
        for n in period_notes
        if n.note_type in ("inbox", "thought")
    ]

    completed_tasks = [
        {"note_id": n.id, "title": n.title, "created": n.created.isoformat()}
        for n in period_notes
        if n.note_type == "task" and n.frontmatter.get("status") == "done"
    ]

    active_projects = [
        {"note_id": n.id, "title": n.title}
        for n in all_notes
        if n.note_type == "project" and n.frontmatter.get("status", "active") == "active"
    ]

    key_themes = _extract_themes(period_notes)

    return ReviewDraft(
        period=period,
        start_date=start_date,
        end_date=target_date,
        total_notes=len(period_notes),
        counts_by_type=counts_by_type,
        new_captures=new_captures,
        completed_tasks=completed_tasks,
        active_projects=active_projects,
        key_themes=key_themes,
    )
