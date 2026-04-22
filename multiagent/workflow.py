from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.state import TaskMetrics, TaskSpec
from multiagent.coordinator import CoordinationResult, StressCoordinator


@dataclass
class MultiAgentWorkflow:
    use_aegis: bool

    def run_task(self, *, task: TaskSpec, repo_root: Path, task_dir: Path, metrics: TaskMetrics) -> CoordinationResult:
        coordinator = StressCoordinator(use_aegis=self.use_aegis)
        return coordinator.run_task(task=task, repo_root=repo_root, task_dir=task_dir, metrics=metrics)
