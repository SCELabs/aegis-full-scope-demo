from __future__ import annotations

from agent.state import TaskSpec


def build_repair_edits(task: TaskSpec, last_error: str) -> list[dict]:
    """Simple repair strategy: retry original hints; keep boundary explicit for future evolution."""
    _ = last_error
    return task.patch_hints
