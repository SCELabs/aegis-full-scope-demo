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
        "task_success_delta": a_summary["tasks_success"] - b_summary["tasks_success"],
        "retries_delta": a_metrics["retries"] - b_metrics["retries"],
        "control_actions_applied": a_metrics["control_actions_applied"],
        "retrieved_kept_delta": a_metrics["retrieved_kept_count"] - b_metrics["retrieved_kept_count"],
    }
    out = results_root / "comparison_latest.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
