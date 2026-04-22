"""Distractor implementations with strong lexical overlap."""

from __future__ import annotations


def route_alert(priority: str, event_type: str, is_customer_blocked: bool = False) -> str:
    normalized_priority = priority.strip().lower()
    normalized_event = event_type.strip().lower()
    if normalized_priority == "high" and normalized_event == "security":
        return "security-watch"
    if is_customer_blocked:
        return "support-escalation"
    return "priority-ops" if normalized_priority == "high" else "standard-ops"


def render_deploy_status(status: str, failed_checks: list[str]) -> dict[str, str]:
    state = status.strip().lower()
    if failed_checks:
        return {"state": "blocked", "message": f"blocked by: {', '.join(failed_checks)}"}
    return {"state": state, "message": state}
