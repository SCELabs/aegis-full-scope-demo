from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from aegis_integration.control_mapper import llm_prompt_prefix, rag_keep_k_from_actions, step_decision
from aegis_integration.llm_control import control_llm
from aegis_integration.rag_control import control_rag
from aegis_integration.step_control import control_step
from agent.executor import execute_edits
from agent.planner import ModelAdapter
from agent.repair import build_repair_edits
from agent.state import TaskMetrics, TaskResult, TaskSpec
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

    def _build_rag_payload(self, task: TaskSpec, retrieval: object, repo_root: Path) -> dict:
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

        retrieval = run_retrieval(repo_root, task.search_queries, keep_k=4)
        metrics.retrieved_candidate_count = len(retrieval.candidates)
        metrics.retrieved_kept_count = len(retrieval.kept_paths)
        metrics.context_duplication_count = retrieval.context_duplication_count
        metrics.relevant_target_file_retrieved = task.expected_target_file in retrieval.kept_paths
        metrics.failing_test_file_retrieved = task.failing_test_file in retrieval.kept_paths

        rag_result = None
        rag_payload_pre = self._build_rag_payload(task, retrieval, repo_root)
        if self.use_aegis:
            rag_result = control_rag(rag_payload_pre)
            keep_k = rag_keep_k_from_actions(rag_result.actions, default_keep_k=4)
            retrieval = run_retrieval(repo_root, task.search_queries, keep_k=keep_k)
            metrics.retrieved_kept_count = len(retrieval.kept_paths)
            metrics.control_actions_applied += len(rag_result.actions)
            metrics.per_scope_action_counts["rag"] += len(rag_result.actions)
            (task_dir / "aegis_result_rag.json").write_text(json.dumps(rag_result.to_dict(), indent=2), encoding="utf-8")

        rag_payload_post = self._build_rag_payload(task, retrieval, repo_root)
        retrieval_diag = {
            "pre_aegis": rag_payload_pre,
            "post_aegis": rag_payload_post,
            "candidate_ranking": rag_payload_post["metadata"]["candidate_summaries"],
        }
        (task_dir / "retrieval_diagnostics.json").write_text(json.dumps(retrieval_diag, indent=2), encoding="utf-8")
        (task_dir / "retrieved_candidates.json").write_text(json.dumps(retrieval.candidates, indent=2), encoding="utf-8")
        (task_dir / "selected_context.json").write_text(
            json.dumps({"kept_paths": retrieval.kept_paths, "retrieved_context": rag_payload_post["retrieved_context"]}, indent=2),
            encoding="utf-8",
        )

        prompt_prefix = ""
        llm_result = None
        if self.use_aegis:
            llm_payload = {
                "base_prompt": "Plan a minimal code patch based on retrieval context and failing tests.",
                "symptoms": ["overspecified_planning"],
                "severity": "medium",
                "input": {"task_id": task.id, "context_paths": retrieval.kept_paths, "candidate_count": len(retrieval.candidates)},
                "metadata": {"task_title": task.title, "target_test": task.target_test},
            }
            llm_result = control_llm(llm_payload)
            prompt_prefix = llm_prompt_prefix(llm_result.actions)
            metrics.control_actions_applied += len(llm_result.actions)
            metrics.per_scope_action_counts["llm"] += len(llm_result.actions)
            (task_dir / "aegis_result_llm.json").write_text(json.dumps(llm_result.to_dict(), indent=2), encoding="utf-8")

        plan = self.model.complete_patch_plan(task, retrieval.context, prompt_prefix=prompt_prefix)
        metrics.llm_calls += 1
        (task_dir / "patch.txt").write_text(json.dumps(plan.edits, indent=2), encoding="utf-8")

        touched: set[str] = set()
        read_files: list[str] = []

        max_attempts = 2
        success = False
        notes = []
        for attempt in range(1, max_attempts + 1):
            for p in retrieval.kept_paths:
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
                full = run_pytest(repo_root)
                metrics.full_test_runs += 1
                if full.passed:
                    notes.append("targeted_and_full_tests_passed")
                else:
                    notes.append("targeted_passed_full_failed")
                break

            if attempt < max_attempts:
                decision = "retry"
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
                        "metadata": {"targeted_stdout": targeted.stdout[:200], "targeted_stderr": targeted.stderr[:200]},
                    }
                    step_result = control_step(step_payload)
                    decision = step_decision(step_result.actions)
                    metrics.control_actions_applied += len(step_result.actions)
                    metrics.per_scope_action_counts["step"] += len(step_result.actions)
                    (task_dir / "aegis_result_step.json").write_text(json.dumps(step_result.to_dict(), indent=2), encoding="utf-8")
                if decision == "replan":
                    metrics.replans += 1
                    plan = self.model.complete_patch_plan(task, retrieval.context, prompt_prefix=prompt_prefix)
                    metrics.llm_calls += 1
                elif decision == "retry":
                    metrics.retries += 1
                    metrics.repair_attempts += 1
                    plan.edits = build_repair_edits(task, last_error=targeted.stdout + targeted.stderr)
                else:
                    notes.append(f"stopped_by_step_control:{decision}")
                    break

        (task_dir / "notes.txt").write_text("\n".join(notes) if notes else "no-notes", encoding="utf-8")
        return TaskResult(task_id=task.id, success=success, notes=";".join(notes), repo_root=repo_root, metrics=metrics, artifacts_dir=task_dir)
