"""Tests for intelligence/contradiction_detector token overlap."""

from __future__ import annotations

from intelligence.contradiction_detector import jaccard_similarity, negation_mismatch, token_set


def test_jaccard_identical() -> None:
    assert jaccard_similarity("use CockroachDB for payments", "use CockroachDB for payments") > 0.5


def test_jaccard_unrelated() -> None:
    assert jaccard_similarity("migrate to kafka", "hire three interns") < 0.2


def test_negation_mismatch() -> None:
    assert negation_mismatch("we will use kafka", "we will not use kafka")


def test_token_set_filters_short_tokens() -> None:
    assert "we" not in token_set("we use kafka")
