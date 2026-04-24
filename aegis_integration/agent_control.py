from __future__ import annotations

from typing import Any

from aegis_integration.result import ScopeResult, normalize_aegis_result


def _normalize_agent_steps(raw_steps: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for step in raw_steps:
        if isinstance(step, str):
            normalized.append({"step_name": step, "step_input": {}})
            continue
        if isinstance(step, dict):
            step_dict = dict(step)
            if "step_name" not in step_dict and "name" in step_dict:
                step_dict["step_name"] = step_dict.get("name")
            if "step_input" not in step_dict and "input" in step_dict:
                step_dict["step_input"] = step_dict.get("input")
            if "step_name" in step_dict and "step_input" not in step_dict:
                step_dict["step_input"] = {}
            normalized.append(step_dict)
    return normalized


def control_agent(payload: dict[str, Any]) -> ScopeResult:
    goal = payload.get("goal", "Complete the task with bounded retries.")
    steps = _normalize_agent_steps(list(payload.get("steps", [])))
    tools = list(payload.get("tools", []))
    metadata = dict(payload.get("metadata", {}))
    session_id = payload.get("session_id") or metadata.get("session_id")
    max_steps = payload.get("max_steps")

    try:
        from aegis import AegisClient  # type: ignore

        client = AegisClient()
        result = client.auto().agent(
            goal=goal,
            steps=steps,
            tools=tools,
            session_id=session_id,
            max_steps=max_steps,
            symptoms=payload.get("symptoms", ["unstable_workflow"]),
            severity=payload.get("severity", "medium"),
            metadata=metadata,
        )
        return normalize_aegis_result(result, scope="agent")
    except Exception as exc:
        planned_steps = steps or ["retrieve_context", "plan_patch", "apply_patch", "validate"]
        allowed_steps = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else len(planned_steps)
        executed = planned_steps[:allowed_steps]
        stop_reason = "completed" if len(executed) >= len(planned_steps) else "max_steps_reached"

        return ScopeResult(
            scope="agent",
            actions=[
                {"type": "set_bounded_loop", "value": allowed_steps},
                {"type": "preserve_task_boundary"},
                {"type": "complete_or_stop_on_max_steps"},
            ],
            trace=[{"event": "fallback", "reason": str(exc)}],
            metrics={"planned_step_count": len(planned_steps)},
            explanation="Fallback agent control: enforce deterministic bounded workflow progression at task boundary.",
            scope_data={
                "mode": "fallback",
                "fallback_reason": str(exc),
                "agent_runtime": {
                    "steps": executed,
                    "tool_calls": [],
                    "stop_reason": stop_reason,
                    "carry_forward_context": [],
                },
            },
            fallback=True,
        )
