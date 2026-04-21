from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ScopeResult:
    scope: str
    actions: list[dict]
    trace: list[dict]
    metrics: dict
    explanation: str
    scope_data: dict
    fallback: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_aegis_result(raw: Any, scope: str) -> ScopeResult:
    payload = raw.to_dict() if hasattr(raw, "to_dict") else (raw if isinstance(raw, dict) else {})
    return ScopeResult(
        scope=payload.get("scope", scope),
        actions=payload.get("actions", []),
        trace=payload.get("trace", []),
        metrics=payload.get("metrics", {}),
        explanation=payload.get("explanation", ""),
        scope_data=payload.get("scope_data", {}),
        fallback=bool(payload.get("used_fallback", False)),
    )


def control_rag(payload: dict) -> ScopeResult:
    try:
        from aegis import AegisClient  # type: ignore

        client = AegisClient()
        result = client.auto().rag(
            query=payload.get("query", ""),
            retrieved_context=payload.get("retrieved_context", []),
            symptoms=payload.get("symptoms", ["retrieval_noise"]),
            severity=payload.get("severity", "medium"),
            metadata=payload.get("metadata", {}),
        )
        return _normalize_aegis_result(result, scope="rag")
    except Exception as exc:  # fallback is expected in offline/demo setups
        context = payload.get("retrieved_context", [])
        action = {"type": "set_keep_k", "value": 3 if len(context) > 4 else 4}
        return ScopeResult(
            scope="rag",
            actions=[action],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"candidate_count": payload.get("metadata", {}).get("candidate_count", 0)},
            explanation="Fallback rag control: tighten context if candidate set is large.",
            scope_data={"mode": "fallback", "fallback_reason": str(exc)},
            fallback=True,
        )
