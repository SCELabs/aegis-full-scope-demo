from __future__ import annotations

from pathlib import Path


def read_file(repo_root: Path, rel_path: str) -> str:
    return (repo_root / rel_path).read_text(encoding="utf-8")
