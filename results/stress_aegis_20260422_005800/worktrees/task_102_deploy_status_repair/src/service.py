"""Stress benchmark target repo with intentionally ambiguous bugs."""

from __future__ import annotations


def route_alert(priority: str, event_type: str, is_customer_blocked: bool = False) -> str:
    normalized_priority = priority.strip().lower()
    normalized_event = event_type.strip().lower()

    if normalized_priority == "high":
        return "priority-ops"
    if normalized_event == "security":
        return "security-watch"
    if is_customer_blocked:
        return "support-escalation"
    return "standard-ops"


def render_deploy_status(status: str, failed_checks: list[str]) -> dict[str, str]:
    state = status.strip().lower()
    if failed_checks:
        return {"state": "needs-repair", "message": f"needs repair: {', '.join(failed_checks)}"}
    return {"state": state, "message": "ready to deploy" if state == "ready" else state}


def choose_merge_strategy(base_branch: str, changed_files: list[str]) -> str:
    docs_only = all(path.startswith("docs/") or path == "README.md" for path in changed_files)
    if base_branch == "main":
        return "safe-rebase"
    if docs_only:
        return "docs-fast-path"
    return "squash"


def pick_review_owner(area: str, has_customer_impact: bool, has_token_scope: bool) -> str:
    normalized = area.strip().lower().replace("_", "-")
    if "billing" in normalized:
        return "billing-ops"
    if "auth" in normalized or has_token_scope:
        return "security-ops"
    if has_customer_impact:
        return "support-ops"
    return "platform-ops"
