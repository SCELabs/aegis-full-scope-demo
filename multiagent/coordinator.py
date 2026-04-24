from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aegis_integration.agent_control import control_agent
from aegis_integration.context_control import control_context
from aegis_integration.control_mapper import StepPolicy, step_policy_from_actions
from aegis_integration.step_control import control_step
from agent.repair import build_repair_edits
from agent.state import TaskMetrics, TaskSpec
from multiagent.executor_agent import execute_plan
from multiagent.planner_agent import choose_plan
from multiagent.retriever_agent import retrieve_with_policy
from multiagent.validator_agent import validate_plan
from tools.test_runner import run_pytest


@dataclass
class CoordinationResult:
    success: bool
    notes: list[str]
    coordination_log: list[dict[str, Any]]
    agent_decisions: list[dict[str, Any]]
    retrieval_diagnostics: dict[str, Any]
    selected_edits: list[dict[str, Any]]
    scope_usage: dict[str, Any]


class StressCoordinator:
    def __init__(self, *, use_aegis: bool) -> None:
        self.use_aegis = use_aegis

    def run_task(
        self,
        *,
        task: TaskSpec,
        repo_root: Path,
        task_dir: Path,
        metrics: TaskMetrics,
    ) -> CoordinationResult:
        keep_k = 5
        prior_feedback = ""
        read_history: set[str] = set()
        touched_files: set[str] = set()
        notes: list[str] = []
        coordination_log: list[dict[str, Any]] = []
        agent_decisions: list[dict[str, Any]] = []
        retrieval_diag: dict[str, Any] = {}
        selected_edits: list[dict[str, Any]] = []
        success = False
        step_policy = StepPolicy(decision="retry")
        step_scope_result: dict[str, Any] | None = None

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
                    "tools": ["retriever_agent", "planner_agent", "executor_agent", "validator_agent"],
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
                context_payload = {
                    "objective": f"Prepare high-signal stress-lane context for task {task.id}.",
                    "messages": [{"role": "user", "content": f"{task.title}: {task.description}"}],
                    "tool_results": [
                        {"tool": "retrieval", "path": path}
                        for path in retriever.retrieval.kept_paths
                    ],
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
                context_result = control_context(context_payload)
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

            read_targets = list(retriever.retrieval.kept_paths)
            if attempt > 1 and touched_files and step_policy.reread_mode == "touched":
                read_targets = [path for path in read_targets if path in touched_files]
            elif attempt > 1 and step_policy.reread_mode == "none":
                read_targets = []

            execution = execute_plan(
                repo_root=repo_root,
                edits=planner.edits,
                read_targets=read_targets,
                already_read=read_history,
                suppress_duplicate_reads=step_policy.suppress_duplicate_reads,
                target_test=task.target_test,
            )
            metrics.targeted_test_runs += 1
            metrics.files_read += len(execution.read_files)
            metrics.files_edited = len(touched_files | set(execution.touched_files))
            touched_files.update(execution.touched_files)
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
                        "rationale": planner.rationale,
                        "candidate_scores": planner.candidate_scores,
                    },
                    "executor": {
                        "patch_results": execution.patch_results,
                        "targeted_test_returncode": execution.targeted_test.returncode,
                    },
                    "validator": asdict(validation),
                }
            )

            if validation.accepted:
                success = True
                selected_edits = planner.edits
                if attempt == 1:
                    metrics.first_pass_success = True
                full = run_pytest(repo_root)
                metrics.full_test_runs += 1
                notes.append("targeted_and_full_tests_passed" if full.passed else "targeted_passed_full_failed")
                coordination_log.append({"attempt": attempt, "decision": "stop", "reason": "validator_accepted"})
                metrics.coordinator_decision_count += 1
                break

            selected_edits = planner.edits
            prior_feedback = validation.feedback
            step_policy = StepPolicy(decision="retry")

            if self.use_aegis:
                step_result = control_step(
                    {
                        "step_name": "stress_coordinator",
                        "step_input": {
                            "task_id": task.id,
                            "attempt": attempt,
                            "max_attempts": 3,
                            "selected_hint_ids": planner.selected_hint_ids,
                            "validator_feedback": validation.feedback,
                        },
                        "symptoms": [
                            "retry_loop",
                            "validator_rejection",
                            "agent_disagreement" if validation.disagreement else "ambiguous_patch",
                        ],
                        "severity": "high" if validation.need_broader_retrieval else "medium",
                        "metadata": {
                            "kept_paths": retriever.retrieval.kept_paths,
                            "target_test": task.target_test,
                        },
                    }
                )
                step_scope_result = step_result.to_dict()
                metrics.control_actions_applied += len(step_result.actions)
                metrics.per_scope_action_counts["step"] += len(step_result.actions)
                metrics.step_scope_activated = True
                metrics.step_scope_activation_count += 1
                if step_result.fallback:
                    metrics.per_scope_fallback_counts["step"] += 1
                else:
                    metrics.per_scope_live_counts["step"] += 1
                step_policy = step_policy_from_actions(step_result.actions, default="retry")
                (task_dir / "aegis_result_step.json").write_text(json.dumps(step_result.to_dict(), indent=2), encoding="utf-8")
            elif validation.need_broader_retrieval:
                step_policy.retrieval_keep_k_delta = 1

            coordinator_decision = "retry"
            if validation.disagreement or validation.prefer_replan:
                coordinator_decision = "replan"
            if self.use_aegis and step_policy.decision in {"retry", "replan", "stop"}:
                coordinator_decision = step_policy.decision
                if validation.prefer_replan and coordinator_decision == "retry":
                    coordinator_decision = "replan"
            elif attempt >= 3:
                coordinator_decision = "stop"

            previous_keep_k = keep_k
            if validation.need_broader_retrieval or step_policy.retrieval_keep_k_delta > 0:
                keep_k += max(1, step_policy.retrieval_keep_k_delta or 1)
                metrics.retrieval_expansion_count += 1

            coordination_log.append(
                {
                    "attempt": attempt,
                    "decision": coordinator_decision,
                    "feedback": validation.feedback,
                    "keep_k_before": previous_keep_k,
                    "keep_k_after": keep_k,
                    "retrieval_expanded": keep_k > previous_keep_k,
                    "step_policy": step_policy.to_dict(),
                    "step_scope_result": step_scope_result,
                }
            )
            metrics.coordinator_decision_count += 1

            if coordinator_decision == "stop":
                notes.append(f"stopped_by_coordinator:{validation.feedback}")
                break
            if coordinator_decision == "replan":
                metrics.replans += 1
                continue

            metrics.retries += 1
            metrics.repair_attempts += 1
            repair_edits = build_repair_edits(task, validation.feedback, repair_mode=planner.planner_policy.repair_mode)
            if repair_edits:
                selected_edits = repair_edits
                execution = execute_plan(
                    repo_root=repo_root,
                    edits=repair_edits,
                    read_targets=[],
                    already_read=read_history,
                    suppress_duplicate_reads=True,
                    target_test=task.target_test,
                )
                metrics.targeted_test_runs += 1
                metrics.files_edited = len(touched_files | set(execution.touched_files))
                touched_files.update(execution.touched_files)
                if execution.targeted_test.passed:
                    success = True
                    notes.append("repair_succeeded")
                    coordination_log.append({"attempt": attempt, "decision": "stop", "reason": "repair_succeeded"})
                    metrics.coordinator_decision_count += 1
                    break

        scope_usage = {
            "rag": {
                "live": metrics.per_scope_live_counts["rag"],
                "fallback": metrics.per_scope_fallback_counts["rag"],
            },
            "llm": {
                "live": metrics.per_scope_live_counts["llm"],
                "fallback": metrics.per_scope_fallback_counts["llm"],
            },
            "step": {
                "live": metrics.per_scope_live_counts["step"],
                "fallback": metrics.per_scope_fallback_counts["step"],
            },
            "context": {
                "live": metrics.per_scope_live_counts["context"],
                "fallback": metrics.per_scope_fallback_counts["context"],
            },
            "agent": {
                "live": metrics.per_scope_live_counts["agent"],
                "fallback": metrics.per_scope_fallback_counts["agent"],
            },
        }
        return CoordinationResult(
            success=success,
            notes=notes,
            coordination_log=coordination_log,
            agent_decisions=agent_decisions,
            retrieval_diagnostics=retrieval_diag,
            selected_edits=selected_edits,
            scope_usage=scope_usage,
        )
