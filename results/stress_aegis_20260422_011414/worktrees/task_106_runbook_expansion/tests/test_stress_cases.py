from __future__ import annotations

from src.service import (
    choose_merge_strategy,
    choose_cache_strategy,
    pick_review_owner,
    resolve_runbook_slug,
    render_deploy_status,
    route_alert,
    select_notification_channel,
)


def test_route_alert_escalates_blocked_security_incidents() -> None:
    assert route_alert("HIGH", "security", is_customer_blocked=True) == "incident-war-room"


def test_render_deploy_status_requires_repair_after_failed_checks() -> None:
    result = render_deploy_status("ready", ["lint", "tests"])
    assert result["state"] == "needs-repair"
    assert "lint" in result["message"]
    assert "tests" in result["message"]


def test_choose_merge_strategy_prefers_docs_fast_path_for_docs_only_mainline_changes() -> None:
    changed = ["docs/runbook.md", "README.md"]
    assert choose_merge_strategy("main", changed) == "docs-fast-path"


def test_pick_review_owner_prefers_security_when_token_scope_is_present() -> None:
    owner = pick_review_owner("billing-auth", has_customer_impact=False, has_token_scope=True)
    assert owner == "security-ops"


def test_select_notification_channel_requires_unacknowledged_customer_critical_path() -> None:
    assert select_notification_channel("critical", is_customer_visible=True, acknowledged=False) == "status-page"


def test_resolve_runbook_slug_expands_to_incident_runbook_for_customer_impact() -> None:
    assert resolve_runbook_slug("payments", "prod", is_customer_impacting=True) == "payments-prod-incident"


def test_choose_cache_strategy_uses_no_cache_for_snapshot_test_runs() -> None:
    assert choose_cache_strategy("snapshot", from_test_suite=True, has_large_payload=False) == "no-cache"
