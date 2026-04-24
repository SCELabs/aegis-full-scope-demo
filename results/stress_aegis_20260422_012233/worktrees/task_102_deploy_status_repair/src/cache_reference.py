"""Distractor cache guidance used by test-dependent stress tasks."""

from __future__ import annotations


def choose_cache_strategy(request_kind: str, from_test_suite: bool, has_large_payload: bool) -> str:
    normalized = request_kind.strip().lower()
    if normalized == "snapshot":
        return "snapshot-cache"
    if has_large_payload:
        return "streaming-cache"
    if from_test_suite:
        return "no-cache"
    return "standard-cache"
