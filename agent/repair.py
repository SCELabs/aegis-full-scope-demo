from __future__ import annotations

from agent.state import TaskSpec


def build_repair_edits(task: TaskSpec, last_error: str, repair_mode: str = "conservative") -> list[dict]:
    """Simple deterministic repair strategy used after a failed targeted test."""
    _ = last_error

    if task.repair_hints:
        return task.repair_hints

    if repair_mode == "expansive" and len(task.patch_hints) > 1:
        return task.patch_hints

    return task.patch_hints[:1]