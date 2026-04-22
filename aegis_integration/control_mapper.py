from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RetrievalPolicy:
    keep_k: int = 4
    boost_path_substrings: list[str] = field(default_factory=list)
    require_target_file: bool = False
    require_failing_test_file: bool = False
    prefer_src: bool = False
    prefer_tests: bool = False
    dedupe_aggressive: bool = False
    expand_retrieval: bool = False
    narrow_retrieval: bool = False
    policy_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlannerPolicy:
    prompt_prefix: str = ""
    strict_old_snippet_match: bool = False
    max_candidate_edits: int = 3
    prefer_minimal_patch: bool = True
    test_context_weight: int = 1
    repair_mode: str = "conservative"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StepPolicy:
    decision: str = "continue"
    run_targeted_only: bool = False
    require_full_validation: bool = True
    reread_mode: str = "all"  # all | touched | none
    suppress_duplicate_reads: bool = False
    retrieval_keep_k_delta: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rag_policy_from_actions(
    actions: list[dict[str, Any]],
    default_keep_k: int,
    target_file: str,
    failing_test_file: str,
) -> RetrievalPolicy:
    policy = RetrievalPolicy(keep_k=default_keep_k)

    for action in actions:
        action_type = str(action.get("type", ""))
        value = action.get("value")

        if action_type == "set_keep_k" and isinstance(value, int) and value > 0:
            policy.keep_k = value
            policy.policy_reasons.append(f"set_keep_k:{value}")
        elif action_type == "boost_paths" and isinstance(value, list):
            policy.boost_path_substrings.extend([str(v) for v in value if v])
            policy.policy_reasons.append("boost_paths")
        elif action_type == "require_target_file":
            policy.require_target_file = True
            policy.policy_reasons.append("require_target_file")
        elif action_type == "require_failing_test_file":
            policy.require_failing_test_file = True
            policy.policy_reasons.append("require_failing_test_file")
        elif action_type == "prefer_src":
            policy.prefer_src = True
            policy.policy_reasons.append("prefer_src")
        elif action_type == "prefer_tests":
            policy.prefer_tests = True
            policy.policy_reasons.append("prefer_tests")
        elif action_type == "dedupe_aggressive":
            policy.dedupe_aggressive = True
            policy.policy_reasons.append("dedupe_aggressive")
        elif action_type == "expand_retrieval":
            policy.expand_retrieval = True
            policy.keep_k += 1
            policy.policy_reasons.append("expand_retrieval")
        elif action_type == "narrow_retrieval":
            policy.narrow_retrieval = True
            policy.keep_k = max(1, policy.keep_k - 1)
            policy.policy_reasons.append("narrow_retrieval")

    if not actions:
        policy.policy_reasons.append("no_actions")

    # Conservative safety defaults for demo stability.
    if target_file:
        policy.require_target_file = True
    if failing_test_file:
        policy.require_failing_test_file = True

    if policy.require_target_file and "require_target_file" not in policy.policy_reasons:
        policy.policy_reasons.append("default_require_target_file")
    if policy.require_failing_test_file and "require_failing_test_file" not in policy.policy_reasons:
        policy.policy_reasons.append("default_require_failing_test_file")

    return policy


def planner_policy_from_llm(scope_result: dict[str, Any]) -> PlannerPolicy:
    actions = scope_result.get("actions", []) or []
    scope_data = scope_result.get("scope_data", {}) or {}
    runtime_config = scope_data.get("runtime_config", {}) if isinstance(scope_data, dict) else {}
    controlled_prompt = scope_data.get("controlled_prompt", "") if isinstance(scope_data, dict) else ""

    policy = PlannerPolicy(
        prompt_prefix=controlled_prompt if isinstance(controlled_prompt, str) else ""
    )

    for action in actions:
        action_type = str(action.get("type", ""))
        value = action.get("value")

        if action_type == "prepend_prompt" and isinstance(value, str):
            policy.prompt_prefix = value + policy.prompt_prefix
        elif action_type == "strict_old_snippet_match":
            policy.strict_old_snippet_match = True
        elif action_type == "set_max_candidate_edits" and isinstance(value, int) and value > 0:
            policy.max_candidate_edits = value
        elif action_type == "prefer_broader_patch":
            policy.prefer_minimal_patch = False
        elif action_type == "weight_test_context" and isinstance(value, int):
            policy.test_context_weight = max(1, value)
        elif action_type == "set_repair_mode" and value in {"conservative", "expansive"}:
            policy.repair_mode = str(value)

    if isinstance(runtime_config, dict):
        if isinstance(runtime_config.get("strict_old_snippet_match"), bool):
            policy.strict_old_snippet_match = runtime_config["strict_old_snippet_match"]
        if isinstance(runtime_config.get("max_candidate_edits"), int) and runtime_config["max_candidate_edits"] > 0:
            policy.max_candidate_edits = runtime_config["max_candidate_edits"]
        if runtime_config.get("patch_mode") == "broader":
            policy.prefer_minimal_patch = False
        if isinstance(runtime_config.get("test_context_weight"), int):
            policy.test_context_weight = max(1, runtime_config["test_context_weight"])
        if runtime_config.get("repair_mode") in {"conservative", "expansive"}:
            policy.repair_mode = str(runtime_config["repair_mode"])

    return policy


def step_policy_from_actions(actions: list[dict[str, Any]], default: str = "continue") -> StepPolicy:
    policy = StepPolicy(decision=default)

    for action in actions:
        action_type = str(action.get("type", ""))
        value = action.get("value")

        if action_type == "decision" and value in {"continue", "retry", "replan", "stop"}:
            policy.decision = str(value)
        elif action_type == "rerun_targeted_only":
            policy.run_targeted_only = True
        elif action_type == "skip_full_validation":
            policy.require_full_validation = False
        elif action_type == "reread_touched_only":
            policy.reread_mode = "touched"
        elif action_type == "reread_none":
            policy.reread_mode = "none"
        elif action_type == "suppress_duplicate_reads":
            policy.suppress_duplicate_reads = True
        elif action_type == "expand_retrieval_next_attempt":
            policy.retrieval_keep_k_delta = max(policy.retrieval_keep_k_delta, 1)
        elif action_type == "narrow_retrieval_next_attempt":
            policy.retrieval_keep_k_delta = min(policy.retrieval_keep_k_delta, -1)

    return policy