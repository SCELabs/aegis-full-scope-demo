from __future__ import annotations

import sys
import types

from aegis_integration.agent_control import control_agent
from aegis_integration.context_control import control_context
from aegis_integration.result import normalize_aegis_result


class _BrokenAuto:
    def context(self, **_: object) -> object:
        raise RuntimeError("context backend unavailable")

    def agent(self, **_: object) -> object:
        raise RuntimeError("agent backend unavailable")


class _BrokenClient:
    def auto(self) -> _BrokenAuto:
        return _BrokenAuto()


class _CaptureAuto:
    def __init__(self, sink: dict[str, object]) -> None:
        self.sink = sink

    def agent(self, **kwargs: object) -> object:
        self.sink["agent_kwargs"] = kwargs
        return {
            "scope": "agent",
            "actions": [{"type": "noop"}],
            "trace": [{"event": "live"}],
            "metrics": {"ok": 1},
            "scope_data": {"mode": "live"},
            "explanation": "ok",
            "used_fallback": False,
        }


class _CaptureClient:
    def __init__(self, sink: dict[str, object]) -> None:
        self.sink = sink

    def auto(self) -> _CaptureAuto:
        return _CaptureAuto(self.sink)


def test_control_context_fallback_when_backend_fails(monkeypatch) -> None:
    fake_module = types.SimpleNamespace(AegisClient=_BrokenClient)
    monkeypatch.setitem(sys.modules, "aegis", fake_module)

    result = control_context(
        {
            "objective": "reduce noise",
            "messages": [{"role": "user", "content": "Fix src/example.py using failing test evidence"}],
            "tool_results": [{"tool": "retrieval", "content": "tests/test_example.py failed"}],
            "constraints": ["remove duplicate/noisy context"],
            "metadata": {
                "expected_target_file": "src/example.py",
                "failing_test_file": "tests/test_example.py",
            },
        }
    )

    assert result.scope == "context"
    assert result.fallback is True
    assert result.metrics["input_message_count"] == 1
    assert result.metrics["input_tool_result_count"] == 1
    assert result.scope_data["mode"] == "fallback"
    assert "cleaned_messages" in result.scope_data
    assert "carry_forward_context" in result.scope_data


def test_control_agent_fallback_when_backend_fails(monkeypatch) -> None:
    fake_module = types.SimpleNamespace(AegisClient=_BrokenClient)
    monkeypatch.setitem(sys.modules, "aegis", fake_module)

    result = control_agent(
        {
            "goal": "Complete bounded task",
            "steps": [
                {"name": "retrieve_context", "input": {"task_id": "task_001"}},
                {"name": "control_context", "input": {"task_id": "task_001"}},
                {"name": "plan_patch", "input": {"task_id": "task_001"}},
            ],
            "max_steps": 2,
            "metadata": {"session_id": "stable:task_001"},
        }
    )

    assert result.scope == "agent"
    assert result.fallback is True
    assert result.metrics["planned_step_count"] == 3
    assert result.scope_data["mode"] == "fallback"
    assert result.scope_data["agent_runtime"]["stop_reason"] == "max_steps_reached"
    assert result.scope_data["agent_runtime"]["tool_calls"] == []


def test_control_agent_live_receives_steps_as_objects(monkeypatch) -> None:
    sink: dict[str, object] = {}
    fake_module = types.SimpleNamespace(AegisClient=lambda: _CaptureClient(sink))
    monkeypatch.setitem(sys.modules, "aegis", fake_module)

    steps = [
        "retrieve_context",
        {"name": "control_context", "input": {"task_id": "task_001"}, "extra": "keep"},
        {"step_name": "plan_patch", "step_input": {"task_id": "task_001"}},
        {"step_name": "apply_patch"},
        {"name": "validate", "input": {"target_test": "tests/test_example.py::test_bugfix"}},
    ]
    result = control_agent({"goal": "do task", "steps": steps, "metadata": {}})

    assert result.scope == "agent"
    assert result.fallback is False
    captured = sink["agent_kwargs"]
    assert isinstance(captured, dict)
    sent_steps = captured["steps"]
    assert isinstance(sent_steps, list)
    assert all(isinstance(step, dict) for step in sent_steps)
    assert sent_steps[0] == {"step_name": "retrieve_context", "step_input": {}}
    assert sent_steps[1]["step_name"] == "control_context"
    assert sent_steps[1]["step_input"] == {"task_id": "task_001"}
    assert sent_steps[1]["extra"] == "keep"
    assert sent_steps[2] == {"step_name": "plan_patch", "step_input": {"task_id": "task_001"}}
    assert sent_steps[3] == {"step_name": "apply_patch", "step_input": {}}
    assert sent_steps[4]["step_name"] == "validate"


def test_normalize_helper_preserves_key_fields() -> None:
    raw = {
        "scope": "context",
        "actions": [{"type": "prioritize"}],
        "trace": [{"event": "ok"}],
        "metrics": {"items": 2},
        "scope_data": {"mode": "live"},
        "explanation": "normalized",
        "used_fallback": False,
    }
    result = normalize_aegis_result(raw, scope="context")
    assert result.scope == "context"
    assert result.actions == [{"type": "prioritize"}]
    assert result.trace == [{"event": "ok"}]
    assert result.metrics == {"items": 2}
    assert result.scope_data == {"mode": "live"}
    assert result.fallback is False
