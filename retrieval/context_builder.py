from __future__ import annotations

from pathlib import Path


def build_context(repo_root: Path, paths: list[str], max_chars: int = 5000) -> str:
    chunks: list[str] = []
    used = 0
    for rel in paths:
        text = (repo_root / rel).read_text(encoding="utf-8")
        block = f"\n# FILE: {rel}\n{text}\n"
        if used + len(block) > max_chars:
            break
        chunks.append(block)
        used += len(block)
    return "\n".join(chunks)
