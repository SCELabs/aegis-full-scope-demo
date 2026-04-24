from __future__ import annotations

from typing import Any

from aegis_integration.result import ScopeResult, normalize_aegis_result


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
        return normalize_aegis_result(result, scope="rag")
    except Exception as exc:
        metadata = payload.get("metadata", {}) or {}
        candidate_count = int(metadata.get("candidate_count", 0))
        target_present = bool(metadata.get("target_file_in_kept", False))
        test_present = bool(metadata.get("failing_test_in_kept", False))
        duplication_count = int(metadata.get("duplication_count", 0))
        target_file = metadata.get("expected_target_file", "")
        failing_test_file = metadata.get("failing_test_file", "")

        actions: list[dict[str, Any]] = []

        if candidate_count > 5:
            actions.append({"type": "narrow_retrieval"})
            actions.append({"type": "set_keep_k", "value": 4})
        else:
            actions.append({"type": "set_keep_k", "value": 5})

        if target_file:
            actions.append({"type": "require_target_file"})
            actions.append({"type": "boost_paths", "value": [target_file]})

        if failing_test_file:
            actions.append({"type": "require_failing_test_file"})
            actions.append({"type": "boost_paths", "value": [failing_test_file]})

        if duplication_count > 0:
            actions.append({"type": "dedupe_aggressive"})

        if not target_present:
            actions.append({"type": "prefer_src"})
        if not test_present:
            actions.append({"type": "prefer_tests"})

        return ScopeResult(
            scope="rag",
            actions=actions,
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={
                "candidate_count": candidate_count,
                "duplication_count": duplication_count,
            },
            explanation="Fallback rag control: require target/test coverage, boost likely paths, and narrow noisy retrieval.",
            scope_data={"mode": "fallback", "fallback_reason": str(exc)},
            fallback=True,
        )
