from __future__ import annotations

from agent.state import AEGIS_SCOPES, TaskMetrics, scope_counter_template, scope_usage_from_counts


def test_scope_counter_template_includes_all_five_scopes() -> None:
    counters = scope_counter_template()
    assert list(counters.keys()) == list(AEGIS_SCOPES)
    assert set(counters.keys()) == {"rag", "llm", "step", "context", "agent"}


def test_task_metrics_include_context_and_agent_counters() -> None:
    metrics = TaskMetrics()
    assert "context" in metrics.per_scope_action_counts
    assert "agent" in metrics.per_scope_action_counts
    assert "context" in metrics.per_scope_live_counts
    assert "agent" in metrics.per_scope_live_counts
    assert "context" in metrics.per_scope_fallback_counts
    assert "agent" in metrics.per_scope_fallback_counts


def test_scope_usage_from_counts_reports_all_scopes() -> None:
    live = scope_counter_template()
    fallback = scope_counter_template()
    live["rag"] = 1
    fallback["step"] = 1
    live["context"] = 2
    fallback["agent"] = 1

    usage = scope_usage_from_counts(live_counts=live, fallback_counts=fallback)
    assert usage == {
        "rag": "live",
        "llm": "not_called",
        "step": "fallback",
        "context": "live",
        "agent": "fallback",
    }
