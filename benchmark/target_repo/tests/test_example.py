"""Tests for the benchmark target repo."""

from __future__ import annotations

import pytest

from src.example import normalize_username, parse_tags, safe_divide


def test_normalize_username_replaces_spaces_with_underscores() -> None:
    assert normalize_username("  Ada Lovelace  ") == "ada_lovelace"


def test_parse_tags_trims_and_drops_empty_entries() -> None:
    assert parse_tags("alpha, beta, ,gamma,, ") == ["alpha", "beta", "gamma"]


def test_safe_divide_returns_result_for_nonzero_denominator() -> None:
    assert safe_divide(10, 2) == 5


def test_safe_divide_raises_for_zero_denominator() -> None:
    with pytest.raises(ValueError, match="denominator"):
        safe_divide(10, 0)
