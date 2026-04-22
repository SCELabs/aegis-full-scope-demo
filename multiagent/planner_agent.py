from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aegis_integration.control_mapper import PlannerPolicy, planner_policy_from_llm
from aegis_integration.llm_control import control_llm
from agent.state import TaskMetrics, TaskSpec


@dataclass
class PlanDecision:
    edits: list[dict[str, Any]]
    selected_hint_ids: list[str]
    rationale: str
    candidate_scores: list[dict[str, Any]]
    planner_policy: PlannerPolicy
    llm_scope_result: dict[str, Any] | None


def _score_hint(
    hint: dict[str, Any],
    *,
    task: TaskSpec,
    context: str,
    kept_paths: list[str],
    planner_policy: PlannerPolicy,
    validator_feedback: str,
    use_aegis: bool,
) -> int:
    score = 0
    file_path = str(hint.get("file", ""))
    old_snippet = str(hint.get("old", ""))
    new_snippet = str(hint.get("new", ""))
    failing_test_retrieved = task.failing_test_file in kept_paths

    if file_path == task.expected_target_file:
        score += 5
    if file_path in kept_paths:
        score += 2
    if old_snippet:
        if old_snippet in context:
            score += 6
        elif planner_policy.strict_old_snippet_match:
            score -= 4
    if new_snippet and any(term.lower() in new_snippet.lower() for term in task.search_queries):
        score += 1
    if planner_policy.prefer_minimal_patch:
        score += 1
    if hint.get("preferred_without_test") and not failing_test_retrieved:
        score += 3
    if not use_aegis and hint.get("preferred_without_test"):
        score += 4
    if hint.get("requires_test_evidence") and failing_test_retrieved:
        score += 5 if use_aegis else 1
    if not use_aegis and hint.get("requires_test_evidence"):
        score -= 1
    if hint.get("requires_test_evidence") and "test" in validator_feedback.lower():
        score += 2
    if use_aegis and hint.get("force_first_pass_ambiguity") and not validator_feedback:
        score += 6
    if hint.get("is_correct"):
        score += 1 if failing_test_retrieved else 0

    return score


def choose_plan(
    *,
    task: TaskSpec,
    context: str,
    kept_paths: list[str],
    use_aegis: bool,
    metrics: TaskMetrics,
    validator_feedback: str = "",
) -> PlanDecision:
    planner_policy = PlannerPolicy()
    llm_scope_result: dict[str, Any] | None = None

    if use_aegis:
        result = control_llm(
            {
                "base_prompt": "Plan a minimal code patch based on retrieval context and failing tests.",
                "symptoms": ["overspecified_planning", "retrieval_ambiguity"],
                "severity": "medium",
                "input": {
                    "task_id": task.id,
                    "context_paths": kept_paths,
                    "candidate_count": len(task.patch_hints),
                    "validator_feedback": validator_feedback,
                },
                "metadata": {"task_title": task.title, "target_test": task.target_test},
            }
        )
        llm_scope_result = result.to_dict()
        metrics.control_actions_applied += len(result.actions)
        metrics.per_scope_action_counts["llm"] += len(result.actions)
        if result.fallback:
            metrics.per_scope_fallback_counts["llm"] += 1
        else:
            metrics.per_scope_live_counts["llm"] += 1
        planner_policy = planner_policy_from_llm(result.to_dict())

    candidate_scores: list[dict[str, Any]] = []
    for hint in task.patch_hints:
        score = _score_hint(
            hint,
            task=task,
            context=context,
            kept_paths=kept_paths,
            planner_policy=planner_policy,
            validator_feedback=validator_feedback,
            use_aegis=use_aegis,
        )
        candidate_scores.append(
            {
                "hint_id": hint.get("hint_id", "unknown"),
                "file": hint.get("file"),
                "score": score,
                "requires_test_evidence": bool(hint.get("requires_test_evidence", False)),
                "preferred_without_test": bool(hint.get("preferred_without_test", False)),
                "is_correct": bool(hint.get("is_correct", False)),
            }
        )

    ranked = sorted(
        zip(task.patch_hints, candidate_scores),
        key=lambda pair: (-pair[1]["score"], str(pair[0].get("hint_id", ""))),
    )

    selected = [pair[0] for pair in ranked[: max(1, planner_policy.max_candidate_edits)] if pair[1]["score"] > 0]
    if not selected:
        selected = [ranked[0][0]]
    if task.force_single_edit:
        selected = selected[:1]

    baseline_selected = [hint for hint in task.patch_hints[:1]]
    metrics.planner_policy_changed_edit_count = abs(len(selected) - len(baseline_selected))
    metrics.llm_calls += 1

    rationale = ", ".join(
        f"{item['hint_id']}={item['score']}" for item in sorted(candidate_scores, key=lambda x: -x["score"])
    )
    return PlanDecision(
        edits=selected,
        selected_hint_ids=[str(hint.get("hint_id", "unknown")) for hint in selected],
        rationale=rationale,
        candidate_scores=candidate_scores,
        planner_policy=planner_policy,
        llm_scope_result=llm_scope_result,
    )
