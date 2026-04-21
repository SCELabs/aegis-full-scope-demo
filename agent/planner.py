from __future__ import annotations

from dataclasses import dataclass

from agent.state import TaskSpec


@dataclass
class Plan:
    prompt: str
    edits: list[dict]


class ModelAdapter:
    """Lightweight model adapter used equally in baseline and aegis runs."""

    def _score_hint(self, hint: dict, task: TaskSpec, context: str) -> int:
        score = 0
        hint_file = str(hint.get("file", ""))
        if hint_file == task.expected_target_file:
            score += 4
        if hint_file in context:
            score += 2
        old_snippet = str(hint.get("old", ""))
        if old_snippet and old_snippet in context:
            score += 5
        if any(term.lower() in str(hint.get("new", "")).lower() for term in task.search_queries):
            score += 1
        return score

    def _planned_edits(self, task: TaskSpec, context: str) -> list[dict]:
        ranked = sorted(task.patch_hints, key=lambda h: self._score_hint(h, task, context), reverse=True)
        selected = [h for h in ranked if self._score_hint(h, task, context) > 0]
        return selected or ranked

    def complete_patch_plan(self, task: TaskSpec, context: str, prompt_prefix: str = "") -> Plan:
        edits = self._planned_edits(task, context)
        prompt = (
            f"{prompt_prefix}Task: {task.title}\nDescription: {task.description}\n"
            f"Candidate patch count: {len(task.patch_hints)}\n"
            f"Chosen edits: {len(edits)}\n"
            f"Context:\n{context[:1200]}\nProduce minimal patch edits."
        )
        return Plan(prompt=prompt, edits=edits)
