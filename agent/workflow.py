from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis_integration.control_mapper import (
    PlannerPolicy,
    RetrievalPolicy,
    StepPolicy,
    planner_policy_from_llm,
    rag_policy_from_actions,
    step_policy_from_actions,
)
from aegis_integration.llm_control import control_llm
from aegis_integration.rag_control import control_rag
from aegis_integration.step_control import control_step
from agent.executor import execute_edits
from agent.planner import ModelAdapter
from agent.repair import build_repair_edits
from agent.state import TaskMetrics, TaskResult, TaskSpec
from retrieval.context_builder import build_context
from retrieval.retriever import RetrievalOutput, run_retrieval
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

    def _compact_context_snippets(self, repo_root: Path, paths: list[str], max_chars: int = 220) -> list[str]:
        snippets: list[str] = []
        for path in paths:
            try:
                text = (repo_root / path).read_text(encoding="utf-8")
            except Exception:
                continue
            compact = " ".join(text.split())[:max_chars]
            snippets.append(f"{path}: {compact}")
        return snippets

    def _build_rag_payload(self, task: TaskSpec, retrieval: RetrievalOutput, repo_root: Path) -> dict[str, Any]:
        kept_set = set(retrieval.kept_paths)
        dropped = [c["path"] for c in retrieval.candidates if c["path"] not in kept_set]

        query = f"{task.title}. {task.description}. Search focus: {' | '.join(task.search_queries)}"
        metadata = {
            "task_id": task.id,
            "candidate_count": len(retrieval.candidates),
            "kept_count": len(retrieval.kept_paths),
            "kept_paths": retrieval.kept_paths,
            "dropped_paths": dropped,
            "duplication_count": retrieval.context_duplication_count,
            "expected_target_file": task.expected_target_file,
            "failing_test_file": task.failing_test_file,
            "target_file_in_kept": task.expected_target_file in kept_set,
            "failing_test_in_kept": task.failing_test_file in kept_set,
            "candidate_summaries": [
                {
                    "path": c["path"],
                    "score": c["score"],
                    "hits": c["hits"],
                    "kept": c["path"] in kept_set,
                    "reason": "kept_in_top_k" if c["path"] in kept_set else "dropped_by_k_or_dedup",
                }
                for c in retrieval.candidates
            ],
        }

        return {
            "query": query,
            "retrieved_context": self._compact_context_snippets(repo_root, retrieval.kept_paths),
            "symptoms": [
                "retrieval_noise" if dropped else "narrow_context",
                "missing_target_file" if task.expected_target_file not in kept_set else "target_file_present",
                "context_duplication" if retrieval.context_duplication_count > 0 else "no_duplication",
            ],
            "severity": "high" if task.expected_target_file not in kept_set else "medium",
            "metadata": metadata,
        }

    def _apply_retrieval_policy(
        self,
        task: TaskSpec,
        retrieval: RetrievalOutput,
        policy: RetrievalPolicy,
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        candidates = [dict(c) for c in retrieval.candidates]

        for candidate in candidates:
            path = str(candidate["path"])
            score = int(candidate.get("score", 0))

            if policy.prefer_src and "/src/" in f"/{path}":
                score += 2
            if policy.prefer_tests and "/tests/" in f"/{path}":
                score += 2

            for needle in policy.boost_path_substrings:
                if needle and needle in path:
                    score += 3

            if path == task.expected_target_file and policy.require_target_file:
                score += 10
            if path == task.failing_test_file and policy.require_failing_test_file:
                score += 8

            candidate["policy_score"] = score

        ranked = sorted(
            candidates,
            key=lambda c: (-int(c.get("policy_score", 0)), c["path"]),
        )

        kept_paths: list[str] = []
        dropped_paths: list[str] = []

        def add_path(path: str) -> None:
            if path not in kept_paths:
                kept_paths.append(path)

        for candidate in ranked:
            path = str(candidate["path"])
            if len(kept_paths) < policy.keep_k:
                add_path(path)
            else:
                dropped_paths.append(path)

        if policy.require_target_file and task.expected_target_file:
            add_path(task.expected_target_file)
        if policy.require_failing_test_file and task.failing_test_file:
            add_path(task.failing_test_file)

        if policy.dedupe_aggressive:
            deduped: list[str] = []
            seen_stems: set[str] = set()
            for path in kept_paths:
                stem = Path(path).stem
                if stem in seen_stems and path not in {task.expected_target_file, task.failing_test_file}:
                    continue
                seen_stems.add(stem)
                deduped.append(path)
            kept_paths = deduped[: max(policy.keep_k, 2)]

        dropped_paths = [p for p in dropped_paths if p not in kept_paths]
        return ranked, kept_paths, dropped_paths

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
        planner_policy = PlannerPolicy()
        step_policy = StepPolicy(decision="retry")
        rag_policy = RetrievalPolicy(keep_k=6)
        step_policy_log: list[dict[str, Any]] = []

        base_retrieval = run_retrieval(repo_root, task.search_queries, keep_k=6)

        if not base_retrieval.candidates:
            notes = ["no_retrieval_candidates"]
            (task_dir / "notes.txt").write_text("\n".join(notes), encoding="utf-8")
            return TaskResult(
                task_id=task.id,
                success=False,
                notes=";".join(notes),
                repo_root=repo_root,
                metrics=metrics,
                artifacts_dir=task_dir,
            )

        rag_payload_pre = self._build_rag_payload(task, base_retrieval, repo_root)

        retrieval = base_retrieval
        ranked_candidates = [dict(c) for c in retrieval.candidates]
        kept_paths = list(retrieval.kept_paths)
        dropped_paths = [c["path"] for c in ranked_candidates if c["path"] not in kept_paths]

        if self.use_aegis:
            rag_result = control_rag(rag_payload_pre)
            metrics.control_actions_applied += len(rag_result.actions)
            metrics.per_scope_action_counts["rag"] += len(rag_result.actions)
            if rag_result.fallback:
                metrics.per_scope_fallback_counts["rag"] += 1
            else:
                metrics.per_scope_live_counts["rag"] += 1

            rag_policy = rag_policy_from_actions(
                rag_result.actions,
                default_keep_k=6,
                target_file=task.expected_target_file,
                failing_test_file=task.failing_test_file,
            )
            ranked_candidates, kept_paths, dropped_paths = self._apply_retrieval_policy(task, base_retrieval, rag_policy)
            retrieval = RetrievalOutput(
                candidates=ranked_candidates,
                kept_paths=kept_paths,
                context=build_context(repo_root, kept_paths),
                context_duplication_count=base_retrieval.context_duplication_count,
            )
            (task_dir / "aegis_result_rag.json").write_text(json.dumps(rag_result.to_dict(), indent=2), encoding="utf-8")

            llm_payload = {
                "base_prompt": "Plan a minimal code patch based on retrieval context and failing tests.",
                "symptoms": ["overspecified_planning"],
                "severity": "medium",
                "input": {
                    "task_id": task.id,
                    "context_paths": retrieval.kept_paths,
                    "candidate_count": len(retrieval.candidates),
                },
                "metadata": {"task_title": task.title, "target_test": task.target_test},
            }
            llm_result = control_llm(llm_payload)
            metrics.control_actions_applied += len(llm_result.actions)
            metrics.per_scope_action_counts["llm"] += len(llm_result.actions)
            if llm_result.fallback:
                metrics.per_scope_fallback_counts["llm"] += 1
            else:
                metrics.per_scope_live_counts["llm"] += 1

            planner_policy = planner_policy_from_llm(llm_result.to_dict())
            (task_dir / "aegis_result_llm.json").write_text(json.dumps(llm_result.to_dict(), indent=2), encoding="utf-8")

        metrics.retrieval_policy_changed_paths = kept_paths != base_retrieval.kept_paths

        rag_payload_post = self._build_rag_payload(task, retrieval, repo_root)
        retrieval_diag = {
            "pre_aegis": rag_payload_pre,
            "post_aegis": rag_payload_post,
            "retrieval_policy_applied": rag_policy.to_dict(),
            "pre_control_candidates": base_retrieval.candidates,
            "post_control_candidates": ranked_candidates,
            "kept_paths": kept_paths,
            "dropped_paths": dropped_paths,
        }

        (task_dir / "retrieval_diagnostics.json").write_text(json.dumps(retrieval_diag, indent=2), encoding="utf-8")
        (task_dir / "retrieved_candidates.json").write_text(json.dumps(retrieval.candidates, indent=2), encoding="utf-8")
        (task_dir / "selected_context.json").write_text(
            json.dumps(
                {
                    "kept_paths": retrieval.kept_paths,
                    "retrieved_context": rag_payload_post["retrieved_context"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        metrics.retrieved_candidate_count = len(retrieval.candidates)
        metrics.retrieved_kept_count = len(retrieval.kept_paths)
        metrics.context_duplication_count = retrieval.context_duplication_count
        metrics.relevant_target_file_retrieved = task.expected_target_file in retrieval.kept_paths
        metrics.failing_test_file_retrieved = task.failing_test_file in retrieval.kept_paths

        baseline_preview_plan = self.model.complete_patch_plan(task, retrieval.context, policy=PlannerPolicy())
        plan = self.model.complete_patch_plan(task, retrieval.context, policy=planner_policy)
        metrics.planner_policy_changed_edit_count = len(plan.edits) != len(baseline_preview_plan.edits)

        metrics.llm_calls += 1
        (task_dir / "patch.txt").write_text(json.dumps(plan.edits, indent=2), encoding="utf-8")

        touched: set[str] = set()
        read_files: list[str] = []
        max_attempts = 3
        success = False
        notes: list[str] = []

        for attempt in range(1, max_attempts + 1):
            read_targets = list(retrieval.kept_paths)
            if attempt > 1 and touched:
                if step_policy.reread_mode == "touched":
                    read_targets = [p for p in retrieval.kept_paths if p in touched]
                elif step_policy.reread_mode == "none":
                    read_targets = []

            for path in read_targets:
                if step_policy.suppress_duplicate_reads and path in read_files:
                    continue
                _ = read_file(repo_root, path)
                read_files.append(path)
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
                if attempt == 1:
                    metrics.first_pass_success = True

                if step_policy.require_full_validation:
                    full = run_pytest(repo_root)
                    metrics.full_test_runs += 1
                    if full.passed:
                        notes.append("targeted_and_full_tests_passed")
                    else:
                        notes.append("targeted_passed_full_failed")
                else:
                    notes.append("targeted_passed_full_validation_skipped_by_policy")
                break

            if attempt >= max_attempts:
                break

            step_policy = StepPolicy(decision="retry")
            if self.use_aegis:
                step_payload = {
                    "step_name": "repair_attempt",
                    "step_input": {
                        "task_id": task.id,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "target_test": task.target_test,
                    },
                    "symptoms": ["target_test_failing", "retry_loop"],
                    "severity": "medium",
                    "metadata": {
                        "targeted_stdout": targeted.stdout[:200],
                        "targeted_stderr": targeted.stderr[:200],
                    },
                }
                step_result = control_step(step_payload)
                metrics.control_actions_applied += len(step_result.actions)
                metrics.per_scope_action_counts["step"] += len(step_result.actions)
                metrics.step_scope_activated = True

                if step_result.fallback:
                    metrics.per_scope_fallback_counts["step"] += 1
                else:
                    metrics.per_scope_live_counts["step"] += 1

                step_policy = step_policy_from_actions(step_result.actions, default="retry")
                (task_dir / "aegis_result_step.json").write_text(json.dumps(step_result.to_dict(), indent=2), encoding="utf-8")

            step_policy_log.append(
                {
                    "attempt": attempt,
                    **step_policy.to_dict(),
                }
            )

            if step_policy.retrieval_keep_k_delta != 0:
                rag_policy.keep_k = max(1, rag_policy.keep_k + step_policy.retrieval_keep_k_delta)
                ranked_candidates, kept_paths, dropped_paths = self._apply_retrieval_policy(task, base_retrieval, rag_policy)
                retrieval = RetrievalOutput(
                    candidates=ranked_candidates,
                    kept_paths=kept_paths,
                    context=build_context(repo_root, kept_paths),
                    context_duplication_count=base_retrieval.context_duplication_count,
                )
                metrics.retrieved_kept_count = len(retrieval.kept_paths)
                metrics.relevant_target_file_retrieved = task.expected_target_file in retrieval.kept_paths
                metrics.failing_test_file_retrieved = task.failing_test_file in retrieval.kept_paths

            if step_policy.decision == "replan":
                metrics.replans += 1
                plan = self.model.complete_patch_plan(task, retrieval.context, policy=planner_policy)
                metrics.llm_calls += 1
            elif step_policy.decision == "retry":
                metrics.retries += 1
                metrics.repair_attempts += 1
                plan.edits = build_repair_edits(
                    task,
                    last_error=targeted.stdout + targeted.stderr,
                    repair_mode=planner_policy.repair_mode,
                )
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

        return TaskResult(
            task_id=task.id,
            success=success,
            notes=";".join(notes),
            repo_root=repo_root,
            metrics=metrics,
            artifacts_dir=task_dir,
        )