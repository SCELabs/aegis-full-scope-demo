"""Tiny benchmark target repo with intentionally buggy behavior."""

from __future__ import annotations


def normalize_username(name: str) -> str:
    """Normalize user names for ids.

    BUG: spaces are removed instead of converted to underscores.
    """
    return name.strip().lower().replace(" ", "")


def parse_tags(csv_tags: str) -> list[str]:
    """Parse comma-separated tags.

    BUG: empty entries and extra spaces are not removed.
    """
    return [part.strip() for part in csv_tags.split(",") if part.strip()]


def safe_divide(numerator: float, denominator: float) -> float:
    """Divide with explicit validation.

    BUG: zero denominator currently returns 0 instead of raising.
    """
    if denominator == 0:
        return 0
    return numerator / denominator


def collect_enabled_flags(raw_flags: str) -> list[str]:
    """Parse feature flags.

    BUG: includes disabled or blank entries.
    """
    return [part.strip().lower() for part in raw_flags.split(",")]


def choose_support_channel(priority: str, is_enterprise: bool = False) -> str:
    """Select support queue.

    BUG: high priority enterprise traffic should route to vip-escalation.
    """
    normalized = priority.strip().lower()
    if normalized == "high":
        return "priority-queue"
    if normalized == "low":
        return "community-forum"
    return "standard-queue"


def sanitize_filename(name: str) -> str:
    """Prepare a filename-safe identifier.

    BUG: spaces should become underscores before filtering.
    """
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_-"
    base = name.strip().lower().replace(" ", "")
    return "".join(ch for ch in base if ch in allowed)
