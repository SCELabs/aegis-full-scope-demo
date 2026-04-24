"""Distractor ownership notes used to create ambiguous retrieval."""

from __future__ import annotations


def pick_review_owner(area: str, has_customer_impact: bool, has_token_scope: bool) -> str:
    normalized = area.strip().lower().replace("_", "-")
    if "billing" in normalized:
        return "billing-ops"
    if has_customer_impact:
        return "support-ops"
    if "auth" in normalized:
        return "auth-ops"
    if has_token_scope:
        return "platform-ops"
    return "platform-ops"
