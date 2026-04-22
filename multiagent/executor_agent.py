from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.executor import execute_edits
from tools.file_read import read_file
from tools.test_runner import TestResult, run_pytest


@dataclass
class ExecutionDecision:
    patch_results: list[dict[str, Any]]
    targeted_test: TestResult
    read_files: list[str]
    touched_files: list[str]
    applied_any: bool


def execute_plan(
    *,
    repo_root: Path,
    edits: list[dict[str, Any]],
    read_targets: list[str],
    already_read: set[str],
    suppress_duplicate_reads: bool,
    target_test: str,
) -> ExecutionDecision:
    read_files: list[str] = []
    for path in read_targets:
        if suppress_duplicate_reads and path in already_read:
            continue
        _ = read_file(repo_root, path)
        already_read.add(path)
        read_files.append(path)

    patch_results = execute_edits(repo_root, edits)
    targeted_test = run_pytest(repo_root, target_test)
    touched_files = [str(edit.get("file", "")) for edit in edits]
    return ExecutionDecision(
        patch_results=[{"applied": result.applied, "reason": result.reason} for result in patch_results],
        targeted_test=targeted_test,
        read_files=read_files,
        touched_files=touched_files,
        applied_any=any(result.applied for result in patch_results),
    )
