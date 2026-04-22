from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaskSpec:
    id: str
    title: str
    description: str
    target_test: str
    expected_target_file: str
    failing_test_file: str
    search_queries: list[str]
    relevant_files: list[str]
    patch_hints: list[dict]
    repair_hints: list[dict] = field(default_factory=list)
    initial_keep_k: int = 5
    force_single_edit: bool = False
    disable_required_file_inclusion_until_retry: bool = False
    prefer_replan_after_disagreement: bool = False


@dataclass
class TaskMetrics:
    llm_calls: int = 0
    retries: int = 0
    replans: int = 0
    duplicate_file_inspections: int = 0
    files_read: int = 0
    files_edited: int = 0
    post_success_unnecessary_steps: int = 0
    targeted_test_runs: int = 0
    full_test_runs: int = 0
    syntax_failures: int = 0
    repair_attempts: int = 0
    control_actions_applied: int = 0

    per_scope_action_counts: dict[str, int] = field(default_factory=lambda: {"rag": 0, "llm": 0, "step": 0})
    per_scope_fallback_counts: dict[str, int] = field(default_factory=lambda: {"rag": 0, "llm": 0, "step": 0})
    per_scope_live_counts: dict[str, int] = field(default_factory=lambda: {"rag": 0, "llm": 0, "step": 0})

    retrieved_candidate_count: int = 0
    retrieved_kept_count: int = 0
    context_duplication_count: int = 0
    relevant_target_file_retrieved: bool = False
    failing_test_file_retrieved: bool = False

    first_pass_success: bool = False
    step_scope_activated: bool = False
    step_scope_activation_count: int = 0
    retrieval_policy_changed_paths: int = 0
    planner_policy_changed_edit_count: int = 0
    planner_executor_disagreement_count: int = 0
    validator_rejection_count: int = 0
    coordinator_decision_count: int = 0
    retrieval_expansion_count: int = 0


@dataclass
class TaskResult:
    task_id: str
    success: bool
    notes: str
    repo_root: Path
    metrics: TaskMetrics
    artifacts_dir: Path
