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


def control_step(payload: dict) -> ScopeResult:
    try:
        from scelabs_aegis import AegisClient  # type: ignore

        client = AegisClient()
        raw = client.auto().step(payload)
        return ScopeResult(
            scope="step",
            actions=raw.get("actions", []),
            trace=raw.get("trace", []),
            metrics=raw.get("metrics", {}),
            explanation=raw.get("explanation", ""),
            scope_data=raw.get("scope_data", {}),
            fallback=False,
        )
    except Exception as exc:
        decision = "retry" if payload.get("attempt", 0) < payload.get("max_attempts", 1) else "stop"
        return ScopeResult(
            scope="step",
            actions=[{"type": "decision", "value": decision}],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"attempt": payload.get("attempt", 0)},
            explanation="Fallback step control based on bounded retries.",
            scope_data={"mode": "fallback"},
            fallback=True,
        )
