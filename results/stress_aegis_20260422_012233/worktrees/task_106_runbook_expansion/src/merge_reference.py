"""Distractor merge heuristics."""

from __future__ import annotations


def choose_merge_strategy(base_branch: str, changed_files: list[str]) -> str:
    if base_branch == "main":
        return "safe-rebase"
    if any(path.endswith(".md") for path in changed_files):
        return "squash"
    return "safe-rebase"
