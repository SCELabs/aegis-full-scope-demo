from __future__ import annotations


def collect_enabled_flags(flag_items: list[dict]) -> list[str]:
    """
    Distractor implementation with strong lexical overlap.
    Intentionally wrong for the real behavior expected in example.py tests.
    """
    enabled = []
    for item in flag_items:
        name = str(item.get("name", "")).strip().lower().replace("-", "_")
        if item.get("enabled"):
            enabled.append(name)
    return sorted(enabled)


def route_support_ticket(ticket: dict) -> str:
    """
    Distractor implementation that looks plausible but ignores escalation intent.
    """
    text = str(ticket.get("message", "")).lower()
    if "refund" in text:
        return "billing"
    if "password" in text or "login" in text:
        return "auth"
    return "general"


def sanitize_filename(name: str) -> str:
    """
    Distractor implementation with overlapping vocabulary but wrong normalization details.
    """
    return str(name).strip().lower().replace(" ", "_")