from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from aegis_integration.agent_control import control_agent
from aegis_integration.context_control import control_context
from agent.repair import build_repair_edits
from agent.state import TaskMetrics, TaskResult, TaskSpec
from multiagent.executor_agent import execute_plan
from multiagent.planner_agent import choose_plan
from multiagent.retriever_agent import retrieve_with_policy
from multiagent.workflow import MultiAgentWorkflow
from multiagent.validator_agent import validate_plan
from tools.test_runner import run_pytest


class StressWorkflowRunner:
    def __init__(self, *, use_aegis: bool, use_multiagent: bool, base_dir: Path) -> None:
        self.use_aegis = use_aegis
        self.use_multiagent = use_multiagent
        self.base_dir = base_dir

    def _load_tasks(self) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        for path in sorted((self.base_dir / "benchmark/tasks_stress").glob("task_*.json")):
            tasks.append(TaskSpec(**json.loads(path.read_text(encoding="utf-8"))))
        return tasks

    def _prepare_repo(self, results_root: Path, task_id: str) -> Path:
        src = self.base_dir / "benchmark/target_repo_stress"
        dst = results_root / "worktrees" / task_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return dst

    def run(self) -> dict[str, object]:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        prefix = "stress_aegis" if self.use_aegis else "stress_baseline"
        run_dir = self.base_dir / "results" / f"{prefix}_{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        task_results: list[dict[str, object]] = []
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
            for key, value in asdict(result.metrics).items():
                if isinstance(value, bool):
                    setattr(aggregate, key, getattr(aggregate, key) or value)
                elif isinstance(value, int):
                    setattr(aggregate, key, getattr(aggregate, key) + value)
                elif isinstance(value, dict):
                    dest = getattr(aggregate, key)
                    for inner_key, inner_value in value.items():
                        dest[inner_key] = dest.get(inner_key, 0) + inner_value

        summary = {
            "mode": "stress_aegis" if self.use_aegis else "stress_baseline",
            "lane": "stress",
            "tasks_total": len(task_results),
            "tasks_success": sum(1 for result in task_results if result["success"]),
            "scope_live_counts": aggregate.per_scope_live_counts,
            "scope_fallback_counts": aggregate.per_scope_fallback_counts,
            "used_live_aegis": any(value > 0 for value in aggregate.per_scope_live_counts.values()),
            "multiagent_enabled": self.use_multiagent,
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

        if self.use_multiagent:
            workflow = MultiAgentWorkflow(use_aegis=self.use_aegis)
            coordination = workflow.run_task(task=task, repo_root=repo_root, task_dir=task_dir, metrics=metrics)
            (task_dir / "retrieval_diagnostics.json").write_text(json.dumps(coordination.retrieval_diagnostics, indent=2), encoding="utf-8")
            (task_dir / "retrieved_candidates.json").write_text(
                json.dumps(coordination.retrieval_diagnostics.get("post_control_candidates", []), indent=2),
                encoding="utf-8",
            )
            (task_dir / "selected_context.json").write_text(
                json.dumps({"kept_paths": coordination.retrieval_diagnostics.get("kept_paths", [])}, indent=2),
                encoding="utf-8",
            )
            (task_dir / "patch.txt").write_text(json.dumps(coordination.selected_edits, indent=2), encoding="utf-8")
            (task_dir / "notes.txt").write_text("\n".join(coordination.notes) if coordination.notes else "no-notes", encoding="utf-8")
            (task_dir / "scope_usage.json").write_text(json.dumps(coordination.scope_usage, indent=2), encoding="utf-8")
            (task_dir / "coordination_log.json").write_text(json.dumps(coordination.coordination_log, indent=2), encoding="utf-8")
            (task_dir / "agent_decisions.json").write_text(json.dumps(coordination.agent_decisions, indent=2), encoding="utf-8")
            return TaskResult(
                task_id=task.id,
                success=coordination.success,
                notes=";".join(coordination.notes),
                repo_root=repo_root,
                metrics=metrics,
                artifacts_dir=task_dir,
            )

        keep_k = task.initial_keep_k
        read_history: set[str] = set()
        touched_files: set[str] = set()
        selected_edits: list[dict] = []
        notes: list[str] = []
        retrieval_diag: dict[str, object] = {}
        scope_usage = {"rag": {}, "llm": {}, "step": {}, "context": {}, "agent": {}}
        coordination_log: list[dict[str, object]] = []
        agent_decisions: list[dict[str, object]] = []
        prior_feedback = ""
        success = False

        if self.use_aegis:
            agent_result = control_agent(
                {
                    "goal": f"Complete coding task {task.id} with minimal patching and bounded retries.",
                    "steps": [
                        {"step_name": "retrieve_context", "step_input": {"task_id": task.id, "attempt": 0}},
                        {"step_name": "control_context", "step_input": {"task_id": task.id, "attempt": 0}},
                        {"step_name": "plan_patch", "step_input": {"task_id": task.id, "attempt": 0}},
                        {"step_name": "apply_patch", "step_input": {"task_id": task.id, "attempt": 0}},
                        {"step_name": "validate", "step_input": {"target_test": task.target_test}},
                    ],
                    "tools": ["retrieve_with_policy", "choose_plan", "execute_plan", "validate_plan"],
                    "session_id": f"stress:{task.id}",
                    "max_steps": 5,
                    "metadata": {
                        "task_id": task.id,
                        "target_test": task.target_test,
                        "expected_target_file": task.expected_target_file,
                        "failing_test_file": task.failing_test_file,
                    },
                }
            )
            metrics.control_actions_applied += len(agent_result.actions)
            metrics.per_scope_action_counts["agent"] += len(agent_result.actions)
            if agent_result.fallback:
                metrics.per_scope_fallback_counts["agent"] += 1
            else:
                metrics.per_scope_live_counts["agent"] += 1
            (task_dir / "aegis_result_agent.json").write_text(json.dumps(agent_result.to_dict(), indent=2), encoding="utf-8")

        for attempt in range(1, 4):
            retriever = retrieve_with_policy(
                task=task,
                repo_root=repo_root,
                use_aegis=self.use_aegis,
                keep_k=keep_k,
                attempt=attempt,
                metrics=metrics,
            )
            retrieval_diag = retriever.diagnostics
            if retriever.scope_result is not None:
                (task_dir / "aegis_result_rag.json").write_text(json.dumps(retriever.scope_result, indent=2), encoding="utf-8")

            if self.use_aegis:
                context_result = control_context(
                    {
                        "objective": f"Prepare high-signal stress-lane context for task {task.id}.",
                        "messages": [{"role": "user", "content": f"{task.title}: {task.description}"}],
                        "tool_results": [{"tool": "retrieval", "path": path} for path in retriever.retrieval.kept_paths],
                        "constraints": [
                            "prioritize target file",
                            "preserve failing test evidence",
                            "remove duplicate/noisy context",
                        ],
                        "symptoms": ["context_noise", "stress_lane"],
                        "severity": "medium",
                        "metadata": {
                            "task_id": task.id,
                            "expected_target_file": task.expected_target_file,
                            "failing_test_file": task.failing_test_file,
                        },
                    }
                )
                metrics.control_actions_applied += len(context_result.actions)
                metrics.per_scope_action_counts["context"] += len(context_result.actions)
                if context_result.fallback:
                    metrics.per_scope_fallback_counts["context"] += 1
                else:
                    metrics.per_scope_live_counts["context"] += 1
                (task_dir / "aegis_result_context.json").write_text(
                    json.dumps(context_result.to_dict(), indent=2),
                    encoding="utf-8",
                )

            planner = choose_plan(
                task=task,
                context=retriever.retrieval.context,
                kept_paths=retriever.retrieval.kept_paths,
                use_aegis=self.use_aegis,
                metrics=metrics,
                validator_feedback=prior_feedback,
            )
            if planner.llm_scope_result is not None:
                (task_dir / "aegis_result_llm.json").write_text(json.dumps(planner.llm_scope_result, indent=2), encoding="utf-8")

            selected_edits = planner.edits
            execution = execute_plan(
                repo_root=repo_root,
                edits=planner.edits,
                read_targets=retriever.retrieval.kept_paths,
                already_read=read_history,
                suppress_duplicate_reads=False,
                target_test=task.target_test,
            )
            metrics.targeted_test_runs += 1
            touched_files.update(execution.touched_files)
            metrics.files_read += len(execution.read_files)
            metrics.files_edited = len(touched_files)
            metrics.duplicate_file_inspections = max(0, metrics.files_read - len(read_history))

            validation = validate_plan(
                task=task,
                plan=planner,
                execution=execution,
                kept_paths=retriever.retrieval.kept_paths,
            )
            if validation.rejected:
                metrics.validator_rejection_count += 1
            if validation.disagreement:
                metrics.planner_executor_disagreement_count += 1

            agent_decisions.append(
                {
                    "attempt": attempt,
                    "retriever": {
                        "kept_paths": retriever.retrieval.kept_paths,
                        "policy": retriever.policy.to_dict(),
                    },
                    "planner": {
                        "selected_hint_ids": planner.selected_hint_ids,
                        "candidate_scores": planner.candidate_scores,
                    },
                    "executor": {
                        "patch_results": execution.patch_results,
                        "targeted_test_returncode": execution.targeted_test.returncode,
                    },
                    "validator": {
                        "accepted": validation.accepted,
                        "rejected": validation.rejected,
                        "disagreement": validation.disagreement,
                        "need_broader_retrieval": validation.need_broader_retrieval,
                        "prefer_replan": validation.prefer_replan,
                        "feedback": validation.feedback,
                    },
                }
            )

            if execution.targeted_test.passed:
                success = True
                if attempt == 1:
                    metrics.first_pass_success = True
                full = run_pytest(repo_root)
                metrics.full_test_runs += 1
                notes.append("targeted_and_full_tests_passed" if full.passed else "targeted_passed_full_failed")
                break

            if attempt == 3:
                notes.append("max_attempts_reached")
                coordination_log.append(
                    {
                        "attempt": attempt,
                        "decision": "stop",
                        "feedback": validation.feedback,
                        "keep_k_before": keep_k,
                        "keep_k_after": keep_k,
                        "retrieval_expanded": False,
                    }
                )
                break

            prior_feedback = validation.feedback
            decision = "replan" if validation.prefer_replan else "retry"
            previous_keep_k = keep_k
            if validation.need_broader_retrieval:
                keep_k += 1
                metrics.retrieval_expansion_count += 1
            coordination_log.append(
                {
                    "attempt": attempt,
                    "decision": decision,
                    "feedback": validation.feedback,
                    "keep_k_before": previous_keep_k,
                    "keep_k_after": keep_k,
                    "retrieval_expanded": keep_k > previous_keep_k,
                }
            )
            metrics.coordinator_decision_count += 1
            if decision == "replan":
                metrics.replans += 1
                continue
            metrics.retries += 1
            metrics.repair_attempts += 1
            repair_edits = build_repair_edits(task, validation.feedback)
            if repair_edits:
                selected_edits = repair_edits
                repair_execution = execute_plan(
                    repo_root=repo_root,
                    edits=repair_edits,
                    read_targets=[],
                    already_read=read_history,
                    suppress_duplicate_reads=True,
                    target_test=task.target_test,
                )
                metrics.targeted_test_runs += 1
                touched_files.update(repair_execution.touched_files)
                metrics.files_edited = len(touched_files)
                if repair_execution.targeted_test.passed:
                    success = True
                    notes.append("repair_succeeded")
                    metrics.coordinator_decision_count += 1
                    coordination_log.append(
                        {
                            "attempt": attempt,
                            "decision": "stop",
                            "reason": "repair_succeeded",
                            "keep_k_before": keep_k,
                            "keep_k_after": keep_k,
                            "retrieval_expanded": False,
                        }
                    )
                    break

        scope_usage["rag"] = {
            "live": metrics.per_scope_live_counts["rag"],
            "fallback": metrics.per_scope_fallback_counts["rag"],
        }
        scope_usage["llm"] = {
            "live": metrics.per_scope_live_counts["llm"],
            "fallback": metrics.per_scope_fallback_counts["llm"],
        }
        scope_usage["step"] = {
            "live": metrics.per_scope_live_counts["step"],
            "fallback": metrics.per_scope_fallback_counts["step"],
        }
        scope_usage["context"] = {
            "live": metrics.per_scope_live_counts["context"],
            "fallback": metrics.per_scope_fallback_counts["context"],
        }
        scope_usage["agent"] = {
            "live": metrics.per_scope_live_counts["agent"],
            "fallback": metrics.per_scope_fallback_counts["agent"],
        }

        (task_dir / "retrieval_diagnostics.json").write_text(json.dumps(retrieval_diag, indent=2), encoding="utf-8")
        (task_dir / "retrieved_candidates.json").write_text(
            json.dumps(retrieval_diag.get("post_control_candidates", []), indent=2),
            encoding="utf-8",
        )
        (task_dir / "selected_context.json").write_text(
            json.dumps({"kept_paths": retrieval_diag.get("kept_paths", [])}, indent=2),
            encoding="utf-8",
        )
        (task_dir / "patch.txt").write_text(json.dumps(selected_edits, indent=2), encoding="utf-8")
        (task_dir / "notes.txt").write_text("\n".join(notes) if notes else "no-notes", encoding="utf-8")
        (task_dir / "scope_usage.json").write_text(json.dumps(scope_usage, indent=2), encoding="utf-8")
        (task_dir / "coordination_log.json").write_text(json.dumps(coordination_log, indent=2), encoding="utf-8")
        (task_dir / "agent_decisions.json").write_text(json.dumps(agent_decisions, indent=2), encoding="utf-8")

        return TaskResult(
            task_id=task.id,
            success=success,
            notes=";".join(notes),
            repo_root=repo_root,
            metrics=metrics,
            artifacts_dir=task_dir,
        )
