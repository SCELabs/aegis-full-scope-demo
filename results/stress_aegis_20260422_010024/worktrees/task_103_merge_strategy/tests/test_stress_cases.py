from __future__ import annotations

from src.service import (
    choose_merge_strategy,
    pick_review_owner,
    render_deploy_status,
    route_alert,
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
