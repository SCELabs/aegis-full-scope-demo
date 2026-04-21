from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileDocument:
    path: str
    content: str


class RepoIndex:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def documents(self) -> list[FileDocument]:
        docs: list[FileDocument] = []
        for path in sorted(self.repo_root.rglob("*.py")):
            rel = path.relative_to(self.repo_root).as_posix()
            docs.append(FileDocument(path=rel, content=path.read_text(encoding="utf-8")))
        return docs
