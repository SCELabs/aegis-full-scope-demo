from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from retrieval.context_builder import build_context
from retrieval.index import RepoIndex
from retrieval.ranker import rank_candidates
from tools.file_search import search_files


@dataclass
class RetrievalOutput:
    candidates: list[dict]
    kept_paths: list[str]
    context: str
    context_duplication_count: int


def run_retrieval(repo_root: Path, queries: list[str], keep_k: int = 4) -> RetrievalOutput:
    idx = RepoIndex(repo_root)
    docs = idx.documents()
    ranked = rank_candidates(docs, queries)

    # also keep explicit tool boundary usage visible
    searched: list[str] = []
    for query in queries:
        searched.extend(search_files(repo_root, query))

    merged_paths: list[str] = [c.path for c in ranked]
    merged_paths.extend(searched)
    dup_count = len(merged_paths) - len(set(merged_paths))

    deduped: list[str] = []
    for path in merged_paths:
        if path not in deduped:
            deduped.append(path)

    kept = deduped[:keep_k]
    context = build_context(repo_root, kept)
    return RetrievalOutput(
        candidates=[{"path": c.path, "score": c.score, "hits": c.hits} for c in ranked],
        kept_paths=kept,
        context=context,
        context_duplication_count=dup_count,
    )
