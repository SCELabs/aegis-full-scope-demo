"""Tests for the benchmark target repo."""

from __future__ import annotations

import pytest

from src.example import (
    choose_support_channel,
    collect_enabled_flags,
    normalize_username,
    parse_tags,
    safe_divide,
    sanitize_filename,
)


def test_normalize_username_replaces_spaces_with_underscores() -> None:
    assert normalize_username("  Ada Lovelace  ") == "ada_lovelace"


def test_parse_tags_trims_and_drops_empty_entries() -> None:
    assert parse_tags("alpha, beta, ,gamma,, ") == ["alpha", "beta", "gamma"]


def test_safe_divide_returns_result_for_nonzero_denominator() -> None:
    assert safe_divide(10, 2) == 5


def test_safe_divide_raises_for_zero_denominator() -> None:
    with pytest.raises(ValueError, match="denominator"):
        safe_divide(10, 0)


def test_collect_enabled_flags_keeps_only_enabled_entries() -> None:
    assert collect_enabled_flags(" ENABLED:Search, disabled:ads, enabled:Billing, ") == [
        "enabled:search",
        "enabled:billing",
    ]


def test_choose_support_channel_escalates_high_enterprise() -> None:
    assert choose_support_channel("HIGH", is_enterprise=True) == "vip-escalation"


def test_sanitize_filename_replaces_spaces_before_filtering() -> None:
    assert sanitize_filename(" Quarterly Report 2026 ") == "quarterly_report_2026"
