from __future__ import annotations

from dataclasses import dataclass

from retrieval.index import FileDocument


@dataclass
class RankedCandidate:
    path: str
    score: int
    hits: list[str]


def rank_candidates(docs: list[FileDocument], query_terms: list[str]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for doc in docs:
        hits = [t for t in query_terms if t.lower() in doc.content.lower() or t.lower() in doc.path.lower()]
        if hits:
            ranked.append(RankedCandidate(path=doc.path, score=len(hits), hits=hits))
    return sorted(ranked, key=lambda c: (-c.score, c.path))
