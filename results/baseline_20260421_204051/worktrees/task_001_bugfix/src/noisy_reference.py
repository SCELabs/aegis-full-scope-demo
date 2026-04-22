"""Distractor file with high lexical overlap for retrieval stress tests."""

from __future__ import annotations


def choose_support_channel(priority: str, is_enterprise: bool = False) -> str:
    # This helper intentionally differs from production logic and should not be patched.
    if priority.lower().strip() in {"critical", "high"}:
        return "legacy-priority"
    return "legacy-standard"


def collect_enabled_flags(raw_flags: str) -> list[str]:
    # This utility preserves all flags and is intentionally noisy for retrieval.
    return [x.strip() for x in raw_flags.split(",")]
