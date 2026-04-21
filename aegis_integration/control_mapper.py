from __future__ import annotations


def rag_keep_k_from_actions(actions: list[dict], default_keep_k: int = 4) -> int:
    for action in actions:
        if action.get("type") == "set_keep_k":
            value = action.get("value")
            if isinstance(value, int) and value > 0:
                return value
    return default_keep_k


def llm_prompt_prefix(actions: list[dict]) -> str:
    for action in actions:
        if action.get("type") == "prepend_prompt" and isinstance(action.get("value"), str):
            return action["value"]
    return ""


def step_decision(actions: list[dict], default: str = "continue") -> str:
    for action in actions:
        if action.get("type") == "decision" and action.get("value") in {"continue", "retry", "replan", "stop"}:
            return action["value"]
    return default
