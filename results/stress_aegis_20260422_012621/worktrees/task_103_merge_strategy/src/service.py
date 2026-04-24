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
        return {"state": state, "message": f"{state}: {', '.join(failed_checks)}"}
    return {"state": state, "message": "ready to deploy" if state == "ready" else state}


def choose_merge_strategy(base_branch: str, changed_files: list[str]) -> str:
    docs_only = all(path.startswith("docs/") or path == "README.md" for path in changed_files)
    if docs_only:
        return "docs-fast-path"
    if base_branch == "main":
        return "safe-rebase"
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


def select_notification_channel(priority: str, is_customer_visible: bool, acknowledged: bool) -> str:
    normalized = priority.strip().lower()
    if normalized == "critical":
        return "pager"
    if is_customer_visible:
        return "status-page"
    if acknowledged:
        return "email"
    return "pager"


def resolve_runbook_slug(team: str, environment: str, is_customer_impacting: bool) -> str:
    normalized_team = team.strip().lower().replace("_", "-")
    if normalized_team == "payments" and environment == "prod":
        return "payments-prod"
    if is_customer_impacting:
        return f"{normalized_team}-customer"
    return f"{normalized_team}-{environment}"


def choose_cache_strategy(request_kind: str, from_test_suite: bool, has_large_payload: bool) -> str:
    normalized = request_kind.strip().lower()
    if normalized == "snapshot":
        return "streaming-cache"
    if has_large_payload:
        return "streaming-cache"
    if from_test_suite:
        return "no-cache"
    return "standard-cache"
