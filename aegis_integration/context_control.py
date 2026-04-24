from __future__ import annotations

from typing import Any

from aegis_integration.result import ScopeResult, normalize_aegis_result


def _to_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("content", "text", "message", "summary"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return str(item)
    return str(item)


def control_context(payload: dict[str, Any]) -> ScopeResult:
    objective = payload.get("objective", "Prioritize context relevant to the active coding task.")
    messages = list(payload.get("messages", []))
    tool_results = list(payload.get("tool_results", []))
    constraints = list(payload.get("constraints", []))
    metadata = dict(payload.get("metadata", {}))

    try:
        from aegis import AegisClient  # type: ignore

        client = AegisClient()
        result = client.auto().context(
            objective=objective,
            messages=messages,
            tool_results=tool_results,
            constraints=constraints,
            symptoms=payload.get("symptoms", ["context_noise"]),
            severity=payload.get("severity", "medium"),
            metadata=metadata,
        )
        return normalize_aegis_result(result, scope="context")
    except Exception as exc:
        protected = {
            str(value)
            for value in [
                metadata.get("expected_target_file"),
                metadata.get("failing_test_file"),
            ]
            if isinstance(value, str) and value
        }

        constraints_text = " ".join(str(x).lower() for x in constraints)
        message_items = [{"source": "message", "value": item} for item in messages]
        tool_items = [{"source": "tool_result", "value": item} for item in tool_results]
        ranked = message_items + tool_items

        def rank_key(item: dict[str, Any]) -> tuple[int, int]:
            text = _to_text(item["value"]).lower()
            score = 0
            if any(token in text for token in protected):
                score += 3
            if "test" in text or "fail" in text:
                score += 2
            if "target" in text or "patch" in text:
                score += 1
            if "duplicate" in constraints_text or "noisy" in constraints_text:
                score += 1
            return (score, -len(text))

        ranked.sort(key=rank_key, reverse=True)
        cleaned = ranked[: max(2, min(6, len(ranked)))]

        cleaned_messages = [item["value"] for item in cleaned if item["source"] == "message"]
        cleaned_tool_results = [item["value"] for item in cleaned if item["source"] == "tool_result"]
        carry_forward_context = [
            _to_text(item["value"])
            for item in cleaned
            if any(token in _to_text(item["value"]).lower() for token in protected) or "test" in _to_text(item["value"]).lower()
        ]

        return ScopeResult(
            scope="context",
            actions=[
                {"type": "prioritize_protected_context"},
                {"type": "drop_duplicate_or_low_relevance_context"},
                {"type": "preserve_failing_test_evidence"},
            ],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={
                "input_message_count": len(messages),
                "input_tool_result_count": len(tool_results),
            },
            explanation="Fallback context control: prioritize high-signal task and failure evidence while reducing noisy context.",
            scope_data={
                "mode": "fallback",
                "fallback_reason": str(exc),
                "cleaned_messages": cleaned_messages or messages,
                "cleaned_tool_results": cleaned_tool_results or tool_results,
                "messages": cleaned_messages or messages,
                "carry_forward_context": carry_forward_context,
            },
            fallback=True,
        )
