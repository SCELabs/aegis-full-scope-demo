from __future__ import annotations

from pathlib import Path

from tools.patch_apply import PatchResult, apply_replace_patch


def execute_edits(repo_root: Path, edits: list[dict]) -> list[PatchResult]:
    results: list[PatchResult] = []
    for edit in edits:
        if edit.get("type") != "replace":
            results.append(PatchResult(applied=False, reason="unsupported_edit_type"))
            continue
        results.append(
            apply_replace_patch(
                repo_root,
                rel_path=edit["file"],
                old=edit["old"],
                new=edit["new"],
            )
        )
    return results
