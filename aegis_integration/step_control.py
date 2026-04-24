from __future__ import annotations

from typing import Any

from aegis_integration.result import ScopeResult, normalize_aegis_result


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
        return normalize_aegis_result(result, scope="step")
    except Exception as exc:
        step_input = payload.get("step_input", {}) or {}
        attempt = int(step_input.get("attempt", payload.get("attempt", 0)))
        max_attempts = int(step_input.get("max_attempts", payload.get("max_attempts", 1)))
        decision = "retry" if attempt < max_attempts else "stop"

        actions: list[dict[str, Any]] = [
            {"type": "decision", "value": decision},
            {"type": "reread_touched_only"},
            {"type": "suppress_duplicate_reads"},
            {"type": "rerun_targeted_only"},
        ]

        if attempt == 1:
            actions.append({"type": "expand_retrieval_next_attempt"})
        else:
            actions.append({"type": "skip_full_validation"})

        return ScopeResult(
            scope="step",
            actions=actions,
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"attempt": attempt},
            explanation="Fallback step control based on bounded retries and loop-waste reduction.",
            scope_data={"mode": "fallback", "fallback_reason": str(exc)},
            fallback=True,
        )
