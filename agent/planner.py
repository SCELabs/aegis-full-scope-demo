from __future__ import annotations

from dataclasses import dataclass

from aegis_integration.control_mapper import PlannerPolicy
from agent.state import TaskSpec


@dataclass
class Plan:
    prompt: str
    edits: list[dict]


class ModelAdapter:
    """Lightweight deterministic planner shared by baseline and Aegis runs."""

    def _score_hint(self, hint: dict, task: TaskSpec, context: str, policy: PlannerPolicy) -> int:
        score = 0
        hint_file = str(hint.get("file", ""))
        old_snippet = str(hint.get("old", ""))
        new_snippet = str(hint.get("new", ""))

        if hint_file == task.expected_target_file:
            score += 5
        if hint_file == task.failing_test_file:
            score += 2 * policy.test_context_weight
        if hint_file and hint_file in context:
            score += 2

        if old_snippet:
            if old_snippet in context:
                score += 6
            elif policy.strict_old_snippet_match:
                score -= 4

        if new_snippet and any(term.lower() in new_snippet.lower() for term in task.search_queries):
            score += 1

        if policy.prefer_minimal_patch and hint_file == task.expected_target_file:
            score += 1

        return score

    def _planned_edits(self, task: TaskSpec, context: str, policy: PlannerPolicy) -> list[dict]:
        ranked = sorted(
            task.patch_hints,
            key=lambda h: self._score_hint(h, task, context, policy),
            reverse=True,
        )

        selected = [h for h in ranked if self._score_hint(h, task, context, policy) > 0]

        if policy.prefer_minimal_patch:
            selected = selected[: policy.max_candidate_edits]
        else:
            selected = selected[: max(policy.max_candidate_edits, len(selected))]

        return selected or ranked[: max(1, policy.max_candidate_edits)]

    def complete_patch_plan(self, task: TaskSpec, context: str, policy: PlannerPolicy | None = None) -> Plan:
        policy = policy or PlannerPolicy()
        edits = self._planned_edits(task, context, policy)
        prompt = (
            f"{policy.prompt_prefix}"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Candidate patch count: {len(task.patch_hints)}\n"
            f"Chosen edits: {len(edits)}\n"
            f"Context:\n{context[:1200]}\n"
            f"Produce minimal patch edits."
        )
        return Plan(prompt=prompt, edits=edits)