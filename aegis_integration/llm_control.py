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


def control_llm(payload: dict) -> ScopeResult:
    try:
        from aegis import AegisClient  # type: ignore

        client = AegisClient()
        result = client.auto().llm(
            base_prompt=payload.get("base_prompt", "Generate a minimal patch plan."),
            symptoms=payload.get("symptoms", ["overspecified_planning"]),
            severity=payload.get("severity", "medium"),
            input=payload.get("input"),
            metadata=payload.get("metadata", {}),
        )
        return _normalize_aegis_result(result, scope="llm")
    except Exception as exc:
        return ScopeResult(
            scope="llm",
            actions=[
                {"type": "prepend_prompt", "value": "Focus on minimal, test-driven patching.\n"},
                {"type": "strict_old_snippet_match"},
                {"type": "set_max_candidate_edits", "value": 2},
                {"type": "set_repair_mode", "value": "conservative"},
            ],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"fallback": 1},
            explanation="Fallback llm control: apply conservative patching guidance.",
            scope_data={"mode": "fallback"},
            fallback=True,
        )
