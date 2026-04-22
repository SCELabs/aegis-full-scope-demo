"""Distractor runbook suggestions for retrieval-expansion pressure."""

from __future__ import annotations


def resolve_runbook_slug(team: str, environment: str, is_customer_impacting: bool) -> str:
    normalized_team = team.strip().lower().replace("_", "-")
    if normalized_team == "payments" and environment == "prod":
        return "payments-prod-customer" if is_customer_impacting else "payments-prod"
    if is_customer_impacting:
        return f"{normalized_team}-customer"
    return f"{normalized_team}-{environment}"
