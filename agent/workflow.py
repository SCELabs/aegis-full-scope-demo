from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from aegis_integration.control_mapper import PlannerPolicy, rag_policy_from_actions, planner_policy_from_llm, step_policy_from_actions
from aegis_integration.llm_control import control_llm
from aegis_integration.rag_control import control_rag
from aegis_integration.step_control import control_step
from agent.executor import execute_edits
from agent.planner import ModelAdapter
from agent.repair import build_repair_edits
from agent.state import TaskMetrics, TaskResult, TaskSpec
from retrieval.context_builder import build_context
from retrieval.retriever import run_retrieval
from tools.file_read import read_file
from tools.test_runner import run_pytest


class WorkflowRunner:
    def __init__(self, use_aegis: bool, base_dir: Path) -> None:
        self.use_aegis = use_aegis
        self.base_dir = base_dir
        self.model = ModelAdapter()

    def _load_tasks(self) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        for path in sorted((self.base_dir / "benchmark/tasks").glob("task_*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            tasks.append(TaskSpec(**raw))
        return tasks

    def _prepare_repo(self, results_root: Path, task_id: str) -> Path:
        src = self.base_dir / "benchmark/target_repo"
        dst = results_root / "worktrees" / task_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return dst

    def run(self) -> dict:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_dir = self.base_dir / "results" / f"{'aegis' if self.use_aegis else 'baseline'}_{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        task_results: list[dict] = []
        aggregate = TaskMetrics()

        for task in self._load_tasks():
            result = self._run_task(task, run_dir)
            task_results.append(
                {
                    "task_id": result.task_id,
                    "success": result.success,
                    "notes": result.notes,
                    "metrics": asdict(result.metrics),
                }
            )
            for k, v in asdict(result.metrics).items():
                if isinstance(v, bool):
                    setattr(aggregate, k, getattr(aggregate, k) or v)
                elif isinstance(v, int):
                    setattr(aggregate, k, getattr(aggregate, k) + v)
                elif isinstance(v, dict):
                    dest = getattr(aggregate, k)
                    for dk, dv in v.items():
                        dest[dk] = dest.get(dk, 0) + dv

        summary = {
            "mode": "aegis" if self.use_aegis else "baseline",
            "tasks_total": len(task_results),
            "tasks_success": sum(1 for x in task_results if x["success"]),
            "scope_live_counts": aggregate.per_scope_live_counts,
            "scope_fallback_counts": aggregate.per_scope_fallback_counts,
            "used_live_aegis": any(v > 0 for v in aggregate.per_scope_live_counts.values()),
        }
        (run_dir / "task_results.json").write_text(json.dumps(task_results, indent=2), encoding="utf-8")
        (run_dir / "metrics.json").write_text(json.dumps(asdict(aggregate), indent=2), encoding="utf-8")
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {"run_dir": run_dir.as_posix(), "summary": summary}

    def _run_task(self, task: TaskSpec, run_dir: Path) -> TaskResult:
        task_dir = run_dir / "tasks" / task.id
        task_dir.mkdir(parents=True, exist_ok=True)
        repo_root = self._prepare_repo(run_dir, task.id)
        metrics = TaskMetrics()

        retrieval = run_retrieval(repo_root, task.search_queries, keep_k=6)
        rag_payload_pre = self._build_rag_payload(task, retrieval, repo_root)

        rag_result = None
        if self.use_aegis:
            rag_result = control_rag({"task_id": task.id, "candidate_count": len(retrieval.candidates), "kept": retrieval.kept_paths})
            keep_k = rag_keep_k_from_actions(rag_result.actions, default_keep_k=4)
            retrieval = run_retrieval(repo_root, task.search_queries, keep_k=keep_k)
            metrics.retrieved_kept_count = len(retrieval.kept_paths)
            metrics.control_actions_applied += len(rag_result.actions)
            metrics.per_scope_action_counts["rag"] += len(rag_result.actions)
            if rag_result.fallback:
                metrics.per_scope_fallback_counts["rag"] += 1
            else:
                metrics.per_scope_live_counts["rag"] += 1
            rag_policy = rag_policy_from_actions(
                rag_result.actions,
                default_keep_k=4,
                target_file=task.expected_target_file,
                failing_test_file=task.failing_test_file,
            )
            (task_dir / "aegis_result_rag.json").write_text(json.dumps(rag_result.to_dict(), indent=2), encoding="utf-8")

        (task_dir / "retrieved_candidates.json").write_text(json.dumps(retrieval.candidates, indent=2), encoding="utf-8")
        (task_dir / "selected_context.json").write_text(json.dumps({"kept_paths": retrieval.kept_paths}, indent=2), encoding="utf-8")

        prompt_prefix = ""
        llm_result = None
        if self.use_aegis:
            llm_result = control_llm({"task_id": task.id, "phase": "plan"})
            prompt_prefix = llm_prompt_prefix(llm_result.actions)
            metrics.control_actions_applied += len(llm_result.actions)
            metrics.per_scope_action_counts["llm"] += len(llm_result.actions)
            if llm_result.fallback:
                metrics.per_scope_fallback_counts["llm"] += 1
            else:
                metrics.per_scope_live_counts["llm"] += 1
            planner_policy = planner_policy_from_llm(llm_result.to_dict())
            (task_dir / "aegis_result_llm.json").write_text(json.dumps(llm_result.to_dict(), indent=2), encoding="utf-8")

        plan = self.model.complete_patch_plan(task, retrieval.context, policy=planner_policy)
        metrics.llm_calls += 1
        (task_dir / "patch.txt").write_text(json.dumps(plan.edits, indent=2), encoding="utf-8")

        touched: set[str] = set()
        read_files: list[str] = []
        max_attempts = 2
        success = False
        notes: list[str] = []
        step_policy_log: list[dict] = []

        for attempt in range(1, max_attempts + 1):
            read_targets = kept_paths
            if attempt > 1 and touched:
                latest_policy = step_policy_log[-1] if step_policy_log else {}
                reread_mode = latest_policy.get("reread_mode", "all")
                if reread_mode == "touched":
                    read_targets = [p for p in kept_paths if p in touched]
                elif reread_mode == "none":
                    read_targets = []

            for p in read_targets:
                if step_policy_log and step_policy_log[-1].get("suppress_duplicate_reads") and p in read_files:
                    continue
                _ = read_file(repo_root, p)
                read_files.append(p)
                metrics.files_read += 1
            metrics.duplicate_file_inspections = len(read_files) - len(set(read_files))

            patch_results = execute_edits(repo_root, plan.edits)
            applied_any = any(r.applied for r in patch_results)
            for edit in plan.edits:
                touched.add(edit["file"])
            metrics.files_edited = len(touched)
            if not applied_any:
                metrics.syntax_failures += 1

            targeted = run_pytest(repo_root, task.target_test)
            metrics.targeted_test_runs += 1
            if targeted.passed:
                success = True
                require_full = True
                if step_policy_log:
                    require_full = step_policy_log[-1].get("require_full_validation", True)
                if require_full:
                    full = run_pytest(repo_root)
                    metrics.full_test_runs += 1
                    if full.passed:
                        notes.append("targeted_and_full_tests_passed")
                    else:
                        notes.append("targeted_passed_full_failed")
                else:
                    notes.append("targeted_passed_full_validation_skipped_by_policy")
                break

            if attempt < max_attempts:
                step_policy = step_policy_from_actions([], default="retry")
                if self.use_aegis:
                    step_result = control_step({"task_id": task.id, "attempt": attempt, "max_attempts": max_attempts})
                    decision = step_decision(step_result.actions)
                    metrics.control_actions_applied += len(step_result.actions)
                    metrics.per_scope_action_counts["step"] += len(step_result.actions)
                    if step_result.fallback:
                        metrics.per_scope_fallback_counts["step"] += 1
                    else:
                        metrics.per_scope_live_counts["step"] += 1
                    step_policy = step_policy_from_actions(step_result.actions, default="retry")
                    (task_dir / "aegis_result_step.json").write_text(json.dumps(step_result.to_dict(), indent=2), encoding="utf-8")

                if step_policy.retrieval_keep_k_delta != 0:
                    rag_policy.keep_k = max(1, rag_policy.keep_k + step_policy.retrieval_keep_k_delta)
                    _, kept_paths, dropped_paths = self._apply_retrieval_policy(task, retrieval, rag_policy)

                step_policy_log.append(
                    {
                        "attempt": attempt,
                        "decision": step_policy.decision,
                        "run_targeted_only": step_policy.run_targeted_only,
                        "require_full_validation": step_policy.require_full_validation,
                        "reread_mode": step_policy.reread_mode,
                        "suppress_duplicate_reads": step_policy.suppress_duplicate_reads,
                        "retrieval_keep_k_delta": step_policy.retrieval_keep_k_delta,
                    }
                )

                if step_policy.decision == "replan":
                    metrics.replans += 1
                    plan = self.model.complete_patch_plan(task, retrieval.context, policy=planner_policy)
                    metrics.llm_calls += 1
                elif step_policy.decision == "retry":
                    metrics.retries += 1
                    metrics.repair_attempts += 1
                    plan.edits = build_repair_edits(task, last_error=targeted.stdout + targeted.stderr, repair_mode=planner_policy.repair_mode)
                else:
                    notes.append(f"stopped_by_step_control:{step_policy.decision}")
                    break

        (task_dir / "step_policy_log.json").write_text(json.dumps(step_policy_log, indent=2), encoding="utf-8")
        task_scope_usage = {
            "rag": "fallback" if metrics.per_scope_fallback_counts["rag"] > 0 else "live" if metrics.per_scope_live_counts["rag"] > 0 else "not_called",
            "llm": "fallback" if metrics.per_scope_fallback_counts["llm"] > 0 else "live" if metrics.per_scope_live_counts["llm"] > 0 else "not_called",
            "step": "fallback" if metrics.per_scope_fallback_counts["step"] > 0 else "live" if metrics.per_scope_live_counts["step"] > 0 else "not_called",
        }
        (task_dir / "scope_usage.json").write_text(json.dumps(task_scope_usage, indent=2), encoding="utf-8")
        (task_dir / "notes.txt").write_text("\n".join(notes) if notes else "no-notes", encoding="utf-8")
        return TaskResult(task_id=task.id, success=success, notes=";".join(notes), repo_root=repo_root, metrics=metrics, artifacts_dir=task_dir)
