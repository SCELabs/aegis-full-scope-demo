from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchResult:
    applied: bool
    reason: str


def apply_replace_patch(repo_root: Path, rel_path: str, old: str, new: str) -> PatchResult:
    path = repo_root / rel_path
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return PatchResult(applied=False, reason="target_snippet_not_found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return PatchResult(applied=True, reason="ok")
