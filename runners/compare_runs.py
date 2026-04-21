from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())


def latest_run(root: Path, prefix: str) -> Path:
    candidates = sorted(root.glob(f"{prefix}_*"))
    if not candidates:
        raise FileNotFoundError(f"No runs found for {prefix}")
    return candidates[-1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    results_root = Path(__file__).resolve().parents[1] / "results"
    b = latest_run(results_root, "baseline")
    a = latest_run(results_root, "aegis")

    b_summary = load_json(b / "summary.json")
    a_summary = load_json(a / "summary.json")
    b_metrics = load_json(b / "metrics.json")
    a_metrics = load_json(a / "metrics.json")

    report = {
        "baseline_run": b.as_posix(),
        "aegis_run": a.as_posix(),
        "success_delta": {
            "tasks_success": a_summary["tasks_success"] - b_summary["tasks_success"],
            "tasks_total": a_summary["tasks_total"] - b_summary["tasks_total"],
        },
        "scope_live_vs_fallback": {
            "live": a_metrics.get("per_scope_live_counts", {}),
            "fallback": a_metrics.get("per_scope_fallback_counts", {}),
            "used_live_aegis": a_summary.get("used_live_aegis", False),
        },
        "control_actions_by_scope": a_metrics.get("per_scope_action_counts", {}),
        "retrieval_changes": {
            "kept_delta": a_metrics["retrieved_kept_count"] - b_metrics["retrieved_kept_count"],
            "target_file_retrieved_delta": int(a_metrics["relevant_target_file_retrieved"]) - int(b_metrics["relevant_target_file_retrieved"]),
            "failing_test_retrieved_delta": int(a_metrics["failing_test_file_retrieved"]) - int(b_metrics["failing_test_file_retrieved"]),
        },
        "loop_behavior_deltas": {
            "duplicate_inspection_delta": a_metrics["duplicate_file_inspections"] - b_metrics["duplicate_file_inspections"],
            "retries_delta": a_metrics["retries"] - b_metrics["retries"],
            "replans_delta": a_metrics["replans"] - b_metrics["replans"],
            "repairs_delta": a_metrics["repair_attempts"] - b_metrics["repair_attempts"],
        },
    }
    out = results_root / "comparison_latest.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
