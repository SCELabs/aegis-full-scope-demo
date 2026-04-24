"""Distractor notification guidance with overlapping vocabulary."""

from __future__ import annotations


def select_notification_channel(priority: str, is_customer_visible: bool, acknowledged: bool) -> str:
    normalized = priority.strip().lower()
    if normalized == "critical" and is_customer_visible:
        return "status-page"
    if acknowledged:
        return "email"
    return "pager"
