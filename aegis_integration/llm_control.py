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


def control_llm(payload: dict) -> ScopeResult:
    try:
        from scelabs_aegis import AegisClient  # type: ignore

        client = AegisClient()
        raw = client.auto().llm(payload)
        return ScopeResult(
            scope="llm",
            actions=raw.get("actions", []),
            trace=raw.get("trace", []),
            metrics=raw.get("metrics", {}),
            explanation=raw.get("explanation", ""),
            scope_data=raw.get("scope_data", {}),
            fallback=False,
        )
    except Exception as exc:
        return ScopeResult(
            scope="llm",
            actions=[{"type": "prepend_prompt", "value": "Focus on minimal, test-driven patching.\n"}],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"fallback": 1},
            explanation="Fallback llm control: apply conservative patching guidance.",
            scope_data={"mode": "fallback"},
            fallback=True,
        )
