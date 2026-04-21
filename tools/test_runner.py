from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def run_pytest(repo_root: Path, target: str | None = None) -> TestResult:
    cmd = ["pytest", "-q"]
    if target:
        cmd.append(target)
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root.as_posix() + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False, env=env)
    return TestResult(command=cmd, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
