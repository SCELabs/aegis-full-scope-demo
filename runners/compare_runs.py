from __future__ import annotations

import json
from pathlib import Path


RESULTS_DIR = Path("results")


def _latest_run(prefix: str) -> Path:
    matches = sorted([p for p in RESULTS_DIR.iterdir() if p.is_dir() and p.name.startswith(prefix)])
    if not matches:
        raise FileNotFoundError(f"No runs found for prefix: {prefix}")
    return matches[-1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    baseline_dir = _latest_run("baseline_")
    aegis_dir = _latest_run("aegis_")

    baseline_summary = _load_json(baseline_dir / "summary.json")
    aegis_summary = _load_json(aegis_dir / "summary.json")
    baseline_metrics = _load_json(baseline_dir / "metrics.json")
    aegis_metrics = _load_json(aegis_dir / "metrics.json")

    output = {
        "baseline_run": baseline_dir.as_posix(),
        "aegis_run": aegis_dir.as_posix(),
        "success_delta": {
            "tasks_success": aegis_summary["tasks_success"] - baseline_summary["tasks_success"],
            "tasks_total": aegis_summary["tasks_total"] - baseline_summary["tasks_total"],
        },
        "scope_live_vs_fallback": {
            "live": aegis_summary["scope_live_counts"],
            "fallback": aegis_summary["scope_fallback_counts"],
            "used_live_aegis": aegis_summary["used_live_aegis"],
        },
        "control_actions_by_scope": aegis_metrics["per_scope_action_counts"],
        "retrieval_changes": {
            "kept_delta": aegis_metrics["retrieved_kept_count"] - baseline_metrics["retrieved_kept_count"],
            "target_file_retrieved_delta": int(aegis_metrics["relevant_target_file_retrieved"]) - int(baseline_metrics["relevant_target_file_retrieved"]),
            "failing_test_retrieved_delta": int(aegis_metrics["failing_test_file_retrieved"]) - int(baseline_metrics["failing_test_file_retrieved"]),
            "retrieval_policy_changed_paths_delta": int(aegis_metrics["retrieval_policy_changed_paths"]) - int(baseline_metrics["retrieval_policy_changed_paths"]),
        },
        "loop_behavior_deltas": {
            "duplicate_inspection_delta": aegis_metrics["duplicate_file_inspections"] - baseline_metrics["duplicate_file_inspections"],
            "retries_delta": aegis_metrics["retries"] - baseline_metrics["retries"],
            "replans_delta": aegis_metrics["replans"] - baseline_metrics["replans"],
            "repairs_delta": aegis_metrics["repair_attempts"] - baseline_metrics["repair_attempts"],
            "step_scope_activated_delta": int(aegis_metrics["step_scope_activated"]) - int(baseline_metrics["step_scope_activated"]),
        },
        "planner_effects": {
            "first_pass_success_delta": int(aegis_metrics["first_pass_success"]) - int(baseline_metrics["first_pass_success"]),
            "planner_policy_changed_edit_count_delta": int(aegis_metrics["planner_policy_changed_edit_count"]) - int(baseline_metrics["planner_policy_changed_edit_count"]),
        },
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()