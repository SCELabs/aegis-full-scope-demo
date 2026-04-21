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


def control_step(payload: dict) -> ScopeResult:
    try:
        from aegis import AegisClient  # type: ignore

        client = AegisClient()
        result = client.auto().step(
            step_name=payload.get("step_name", "retry_loop"),
            step_input=payload.get("step_input", {}),
            symptoms=payload.get("symptoms", ["retry_loop"]),
            severity=payload.get("severity", "medium"),
            metadata=payload.get("metadata", {}),
        )
        return _normalize_aegis_result(result, scope="step")
    except Exception as exc:
        step_input = payload.get("step_input", {})
        attempt = step_input.get("attempt", payload.get("attempt", 0))
        max_attempts = step_input.get("max_attempts", payload.get("max_attempts", 1))
        decision = "retry" if attempt < max_attempts else "stop"
        return ScopeResult(
            scope="step",
            actions=[
                {"type": "decision", "value": decision},
                {"type": "reread_touched_only"},
                {"type": "suppress_duplicate_reads"},
                {"type": "rerun_targeted_only"},
            ],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"attempt": attempt},
            explanation="Fallback step control based on bounded retries.",
            scope_data={"mode": "fallback", "fallback_reason": str(exc)},
            fallback=True,
        )
