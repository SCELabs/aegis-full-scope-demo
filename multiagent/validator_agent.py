from __future__ import annotations

from dataclasses import dataclass

from agent.state import TaskSpec
from multiagent.executor_agent import ExecutionDecision
from multiagent.planner_agent import PlanDecision


@dataclass
class ValidationDecision:
    accepted: bool
    rejected: bool
    disagreement: bool
    need_broader_retrieval: bool
    feedback: str


def validate_plan(
    *,
    task: TaskSpec,
    plan: PlanDecision,
    execution: ExecutionDecision,
    kept_paths: list[str],
) -> ValidationDecision:
    if execution.targeted_test.passed:
        return ValidationDecision(
            accepted=True,
            rejected=False,
            disagreement=False,
            need_broader_retrieval=False,
            feedback="Targeted test passed.",
        )

    selected = [hint for hint in task.patch_hints if str(hint.get("hint_id", "")) in plan.selected_hint_ids]
    selected_correct = any(bool(hint.get("is_correct", False)) for hint in selected)
    disagreement = not selected_correct
    missing_test_evidence = task.failing_test_file not in kept_paths

    if not execution.applied_any:
        feedback = "Patch did not apply cleanly; replan with current file state."
    elif disagreement and missing_test_evidence:
        feedback = "Planner selected an ambiguous hint without test evidence; broaden retrieval and replan."
    elif disagreement:
        feedback = "Validator rejected the chosen edit; test evidence points to a different patch."
    else:
        feedback = "Patch applied but the targeted test still fails; retry with a repair edit."

    return ValidationDecision(
        accepted=False,
        rejected=True,
        disagreement=disagreement,
        need_broader_retrieval=missing_test_evidence or disagreement,
        feedback=feedback,
    )
