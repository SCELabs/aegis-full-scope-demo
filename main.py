from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(script: str) -> None:
    subprocess.run(["python", script], cwd=Path(__file__).parent, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aegis full-scope demo runner")
    parser.add_argument("mode", choices=["baseline", "aegis", "compare", "all"])
    args = parser.parse_args()

    if args.mode in {"baseline", "all"}:
        run("runners/run_baseline.py")
    if args.mode in {"aegis", "all"}:
        run("runners/run_aegis.py")
    if args.mode in {"compare", "all"}:
        run("runners/compare_runs.py")
