from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ScopeResult:
    scope: str
    actions: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    metrics: dict[str, Any]
    explanation: str
    scope_data: dict[str, Any]
    fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_aegis_result(raw: Any, scope: str) -> ScopeResult:
    payload = raw.to_dict() if hasattr(raw, "to_dict") else (raw if isinstance(raw, dict) else {})
    return ScopeResult(
        scope=str(payload.get("scope", scope)),
        actions=list(payload.get("actions", [])),
        trace=list(payload.get("trace", [])),
        metrics=dict(payload.get("metrics", {})),
        explanation=str(payload.get("explanation", "")),
        scope_data=dict(payload.get("scope_data", {})),
        fallback=bool(payload.get("used_fallback", False)),
    )
