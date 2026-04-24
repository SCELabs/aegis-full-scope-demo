from __future__ import annotations

from aegis_integration.result import ScopeResult, normalize_aegis_result

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
        return normalize_aegis_result(result, scope="llm")
    except Exception as exc:
        return ScopeResult(
            scope="llm",
            actions=[
                {"type": "prepend_prompt", "value": "Focus on minimal, test-driven patching.\n"},
                {"type": "strict_old_snippet_match"},
                {"type": "set_max_candidate_edits", "value": 2},
                {"type": "set_repair_mode", "value": "conservative"},
                {"type": "weight_test_context", "value": 2},
            ],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"fallback": 1},
            explanation="Fallback llm control: conservative patch selection with stronger test-context weighting.",
            scope_data={
                "mode": "fallback",
                "fallback_reason": str(exc),
                "runtime_config": {
                    "strict_old_snippet_match": True,
                    "max_candidate_edits": 2,
                    "patch_mode": "minimal",
                    "test_context_weight": 2,
                    "repair_mode": "conservative",
                },
                "controlled_prompt": "Focus on minimal, test-driven patching.\n",
            },
            fallback=True,
        )
