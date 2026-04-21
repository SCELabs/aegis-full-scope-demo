from __future__ import annotations

from dataclasses import asdict, dataclass


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


def control_rag(payload: dict) -> ScopeResult:
    try:
        from scelabs_aegis import AegisClient  # type: ignore

        client = AegisClient()
        raw = client.auto().rag(payload)
        return ScopeResult(
            scope="rag",
            actions=raw.get("actions", []),
            trace=raw.get("trace", []),
            metrics=raw.get("metrics", {}),
            explanation=raw.get("explanation", ""),
            scope_data=raw.get("scope_data", {}),
            fallback=False,
        )
    except Exception as exc:  # fallback is expected in offline/demo setups
        action = {"type": "set_keep_k", "value": 3 if payload.get("candidate_count", 0) > 4 else 4}
        return ScopeResult(
            scope="rag",
            actions=[action],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"candidate_count": payload.get("candidate_count", 0)},
            explanation="Fallback rag control: tighten context if candidate set is large.",
            scope_data={"mode": "fallback"},
            fallback=True,
        )
