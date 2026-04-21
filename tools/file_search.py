from __future__ import annotations

from pathlib import Path


def search_files(repo_root: Path, query: str) -> list[str]:
    """Simple text search across python files in the benchmark repo."""
    results: list[str] = []
    lowered = query.lower()
    for path in sorted(repo_root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8")
        if lowered in text.lower() or lowered in rel.lower():
            results.append(rel)
    return results
