from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis_integration.control_mapper import RetrievalPolicy, rag_policy_from_actions
from aegis_integration.rag_control import control_rag
from agent.state import TaskMetrics, TaskSpec
from retrieval.context_builder import build_context
from retrieval.retriever import RetrievalOutput, run_retrieval


@dataclass
class RetrieverDecision:
    retrieval: RetrievalOutput
    diagnostics: dict[str, Any]
    policy: RetrievalPolicy
    scope_result: dict[str, Any] | None


def _compact_context_snippets(repo_root: Path, paths: list[str], max_chars: int = 220) -> list[str]:
    snippets: list[str] = []
    for path in paths:
        try:
            text = (repo_root / path).read_text(encoding="utf-8")
        except Exception:
            continue
        compact = " ".join(text.split())[:max_chars]
        snippets.append(f"{path}: {compact}")
    return snippets


def _build_rag_payload(task: TaskSpec, retrieval: RetrievalOutput, repo_root: Path) -> dict[str, Any]:
    kept_set = set(retrieval.kept_paths)
    dropped = [c["path"] for c in retrieval.candidates if c["path"] not in kept_set]
    return {
        "query": f"{task.title}. {task.description}. Search focus: {' | '.join(task.search_queries)}",
        "retrieved_context": _compact_context_snippets(repo_root, retrieval.kept_paths),
        "symptoms": [
            "retrieval_noise" if dropped else "narrow_context",
            "missing_target_file" if task.expected_target_file not in kept_set else "target_file_present",
            "missing_failing_test" if task.failing_test_file not in kept_set else "failing_test_present",
            "context_duplication" if retrieval.context_duplication_count > 0 else "no_duplication",
        ],
        "severity": "high" if task.failing_test_file not in kept_set or task.expected_target_file not in kept_set else "medium",
        "metadata": {
            "task_id": task.id,
            "candidate_count": len(retrieval.candidates),
            "kept_count": len(retrieval.kept_paths),
            "kept_paths": retrieval.kept_paths,
            "duplication_count": retrieval.context_duplication_count,
            "expected_target_file": task.expected_target_file,
            "failing_test_file": task.failing_test_file,
            "target_file_in_kept": task.expected_target_file in kept_set,
            "failing_test_in_kept": task.failing_test_file in kept_set,
        },
    }


def _apply_retrieval_policy(
    task: TaskSpec,
    retrieval: RetrievalOutput,
    policy: RetrievalPolicy,
    *,
    allow_required_inclusion: bool,
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

    ranked = sorted(candidates, key=lambda c: (-int(c.get("policy_score", 0)), c["path"]))
    kept_paths: list[str] = []
    dropped_paths: list[str] = []

    for candidate in ranked:
        path = str(candidate["path"])
        if len(kept_paths) < policy.keep_k:
            if path not in kept_paths:
                kept_paths.append(path)
        else:
            dropped_paths.append(path)

    if allow_required_inclusion and policy.require_target_file and task.expected_target_file and task.expected_target_file not in kept_paths:
        kept_paths.append(task.expected_target_file)
    if allow_required_inclusion and policy.require_failing_test_file and task.failing_test_file and task.failing_test_file not in kept_paths:
        kept_paths.append(task.failing_test_file)

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

    dropped_paths = [path for path in dropped_paths if path not in kept_paths]
    return ranked, kept_paths, dropped_paths


def retrieve_with_policy(
    *,
    task: TaskSpec,
    repo_root: Path,
    use_aegis: bool,
    keep_k: int,
    attempt: int,
    metrics: TaskMetrics,
) -> RetrieverDecision:
    base_retrieval = run_retrieval(repo_root, task.search_queries, keep_k=keep_k)
    rag_payload_pre = _build_rag_payload(task, base_retrieval, repo_root)
    policy = RetrievalPolicy(keep_k=keep_k)
    scope_result: dict[str, Any] | None = None

    ranked_candidates = [dict(c) for c in base_retrieval.candidates]
    kept_paths = list(base_retrieval.kept_paths)
    dropped_paths = [c["path"] for c in ranked_candidates if c["path"] not in kept_paths]

    if use_aegis:
        result = control_rag(rag_payload_pre)
        scope_result = result.to_dict()
        metrics.control_actions_applied += len(result.actions)
        metrics.per_scope_action_counts["rag"] += len(result.actions)
        if result.fallback:
            metrics.per_scope_fallback_counts["rag"] += 1
        else:
            metrics.per_scope_live_counts["rag"] += 1

        policy = rag_policy_from_actions(
            result.actions,
            default_keep_k=keep_k,
            target_file=task.expected_target_file,
            failing_test_file=task.failing_test_file,
        )
        allow_required_inclusion = not (task.disable_required_file_inclusion_until_retry and attempt == 1)
        ranked_candidates, kept_paths, dropped_paths = _apply_retrieval_policy(
            task,
            base_retrieval,
            policy,
            allow_required_inclusion=allow_required_inclusion,
        )

    retrieval = RetrievalOutput(
        candidates=ranked_candidates,
        kept_paths=kept_paths,
        context=build_context(repo_root, kept_paths),
        context_duplication_count=base_retrieval.context_duplication_count,
    )

    metrics.retrieved_candidate_count = len(retrieval.candidates)
    metrics.retrieved_kept_count = len(retrieval.kept_paths)
    metrics.context_duplication_count = retrieval.context_duplication_count
    metrics.relevant_target_file_retrieved = task.expected_target_file in retrieval.kept_paths
    metrics.failing_test_file_retrieved = task.failing_test_file in retrieval.kept_paths
    metrics.retrieval_policy_changed_paths = len(set(base_retrieval.kept_paths) ^ set(retrieval.kept_paths))

    diagnostics = {
        "pre_aegis": rag_payload_pre,
        "post_aegis": _build_rag_payload(task, retrieval, repo_root),
        "retrieval_policy_applied": policy.to_dict(),
        "pre_control_candidates": base_retrieval.candidates,
        "post_control_candidates": ranked_candidates,
        "kept_paths": kept_paths,
        "dropped_paths": dropped_paths,
    }
    return RetrieverDecision(retrieval=retrieval, diagnostics=diagnostics, policy=policy, scope_result=scope_result)
