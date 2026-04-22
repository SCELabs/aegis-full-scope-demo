from __future__ import annotations

import json
from pathlib import Path


RESULTS_DIR = Path("results")


def _latest_run(prefix: str) -> Path:
    matches = sorted([path for path in RESULTS_DIR.iterdir() if path.is_dir() and path.name.startswith(prefix)])
    if not matches:
        raise FileNotFoundError(f"No runs found for prefix: {prefix}")
    return matches[-1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    baseline_dir = _latest_run("stress_baseline_")
    aegis_dir = _latest_run("stress_aegis_")

    baseline_summary = _load_json(baseline_dir / "summary.json")
    aegis_summary = _load_json(aegis_dir / "summary.json")
    baseline_metrics = _load_json(baseline_dir / "metrics.json")
    aegis_metrics = _load_json(aegis_dir / "metrics.json")

    output = {
        "baseline_run": baseline_dir.as_posix(),
        "aegis_run": aegis_dir.as_posix(),
        "success": {
            "baseline": baseline_summary["tasks_success"],
            "aegis": aegis_summary["tasks_success"],
            "delta": aegis_summary["tasks_success"] - baseline_summary["tasks_success"],
        },
        "stress_loop_metrics": {
            "first_pass_success_delta": aegis_metrics["first_pass_success"] - baseline_metrics["first_pass_success"],
            "retries_delta": aegis_metrics["retries"] - baseline_metrics["retries"],
            "replans_delta": aegis_metrics["replans"] - baseline_metrics["replans"],
            "repair_attempts_delta": aegis_metrics["repair_attempts"] - baseline_metrics["repair_attempts"],
            "duplicate_file_inspections_delta": aegis_metrics["duplicate_file_inspections"] - baseline_metrics["duplicate_file_inspections"],
            "step_scope_activation_count_delta": aegis_metrics["step_scope_activation_count"] - baseline_metrics["step_scope_activation_count"],
            "planner_policy_changed_edit_count_delta": aegis_metrics["planner_policy_changed_edit_count"] - baseline_metrics["planner_policy_changed_edit_count"],
            "retrieval_policy_changed_paths_delta": aegis_metrics["retrieval_policy_changed_paths"] - baseline_metrics["retrieval_policy_changed_paths"],
        },
        "retrieval_coverage": {
            "target_file_retrieved_delta": int(aegis_metrics["relevant_target_file_retrieved"]) - int(baseline_metrics["relevant_target_file_retrieved"]),
            "failing_test_retrieved_delta": int(aegis_metrics["failing_test_file_retrieved"]) - int(baseline_metrics["failing_test_file_retrieved"]),
        },
        "scope_usage": {
            "baseline_live": baseline_summary["scope_live_counts"],
            "baseline_fallback": baseline_summary["scope_fallback_counts"],
            "aegis_live": aegis_summary["scope_live_counts"],
            "aegis_fallback": aegis_summary["scope_fallback_counts"],
        },
        "multiagent_metrics": {
            "planner_executor_disagreement_delta": aegis_metrics["planner_executor_disagreement_count"] - baseline_metrics["planner_executor_disagreement_count"],
            "validator_rejection_delta": aegis_metrics["validator_rejection_count"] - baseline_metrics["validator_rejection_count"],
            "coordinator_decision_delta": aegis_metrics["coordinator_decision_count"] - baseline_metrics["coordinator_decision_count"],
            "multiagent_enabled": aegis_summary.get("multiagent_enabled", False),
        },
    }

    output_path = RESULTS_DIR / "comparison_stress_latest.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
