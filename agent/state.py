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
    retrieved_candidate_count: int = 0
    retrieved_kept_count: int = 0
    context_duplication_count: int = 0
    relevant_target_file_retrieved: bool = False
    failing_test_file_retrieved: bool = False


@dataclass
class TaskResult:
    task_id: str
    success: bool
    notes: str
    repo_root: Path
    metrics: TaskMetrics
    artifacts_dir: Path
