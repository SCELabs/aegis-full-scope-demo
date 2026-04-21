from __future__ import annotations

from dataclasses import dataclass

from agent.state import TaskSpec


@dataclass
class Plan:
    prompt: str
    edits: list[dict]


class ModelAdapter:
    """Lightweight model adapter used equally in baseline and aegis runs."""

    def complete_patch_plan(self, task: TaskSpec, context: str, prompt_prefix: str = "") -> Plan:
        prompt = (
            f"{prompt_prefix}Task: {task.title}\nDescription: {task.description}\n"
            f"Context:\n{context[:1200]}\nProduce minimal patch edits."
        )
        return Plan(prompt=prompt, edits=task.patch_hints)
