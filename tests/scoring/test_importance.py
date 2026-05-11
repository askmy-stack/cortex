"""Tests for scoring/importance.py.

Tests cover:
- Event type base score ordering (decision > exception > rationale > update)
- Person signal (named authors boost score)
- System signal (named systems boost score)
- Rationale signal (explicit rationale boosts score)
- Content length bell curve
- Supersedes signal
- Weighted combination produces 0–1 range
- Band classification (discard / compress / full / full_notify)
- score() mutates importance_score on DecisionEvent
- score_with_breakdown() does NOT mutate
"""

from __future__ import annotations

from datetime import UTC, datetime

from scoring.importance import (
    ImportanceScorer,
    _importance_band,
    _score_content_length,
    _score_event_type,
    _score_persons,
    _score_rationale,
    _score_supersedes,
    _score_systems,
)
from shared.models import (
    IMPORTANCE_COMPRESS,
    IMPORTANCE_DISCARD,
    IMPORTANCE_FULL,
    DecisionEvent,
    Provenance,
)

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
WORKSPACE_ID = "test-workspace"


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────


def _make_decision(
    event_type: str = "decision",
    made_by: list[str] | None = None,
    affects: list[str] | None = None,
    rationale: list[str] | None = None,
    content: str = "We decided to migrate payments to CockroachDB for scale.",
    replaces: str | None = None,
) -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id="raw-001",
        workspace_id=WORKSPACE_ID,
        event_type=event_type,  # type: ignore[arg-type]
        content=content,
        made_by=["priya@company.com"] if made_by is None else made_by,
        affects=["payments-service"] if affects is None else affects,
        rationale=["Scale ceiling at 10M txn/day"] if rationale is None else rationale,
        replaces=replaces,
        extraction_confidence=0.90,
        importance_score=0.0,
        trust_score=0.0,
        provenance=Provenance(
            source="slack",
            channel="C-engineering",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-001",
        ),
        extracted_at=NOW,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Component scorers
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreEventType:
    def test_decision_scores_highest(self) -> None:
        assert _score_event_type("decision") == 1.0

    def test_exception_below_decision(self) -> None:
        assert _score_event_type("exception") < _score_event_type("decision")

    def test_rationale_below_exception(self) -> None:
        assert _score_event_type("rationale") < _score_event_type("exception")

    def test_update_scores_lowest_of_known(self) -> None:
        assert _score_event_type("update") <= _score_event_type("escalation")

    def test_unknown_type_returns_default(self) -> None:
        score = _score_event_type("unknown_type")
        assert 0.0 <= score <= 1.0

    def test_ordering(self) -> None:
        scores = [
            _score_event_type(t)
            for t in ["decision", "exception", "rationale", "escalation", "update"]
        ]
        assert scores == sorted(scores, reverse=True)


class TestScorePersons:
    def test_empty_made_by_returns_low_score(self) -> None:
        assert _score_persons([]) < 0.5

    def test_unknown_author_returns_low_score(self) -> None:
        assert _score_persons(["unknown"]) < 0.5

    def test_named_author_boosts_score(self) -> None:
        assert _score_persons(["priya@company.com"]) > _score_persons([])

    def test_two_authors_higher_than_one(self) -> None:
        assert _score_persons(["alice@", "bob@"]) > _score_persons(["alice@"])

    def test_caps_at_1_0(self) -> None:
        assert _score_persons(["a@", "b@", "c@", "d@", "e@"]) <= 1.0


class TestScoreSystems:
    def test_empty_affects_returns_low_score(self) -> None:
        assert _score_systems([]) < 0.5

    def test_named_system_boosts_score(self) -> None:
        assert _score_systems(["payments-service"]) > _score_systems([])

    def test_two_systems_higher_than_one(self) -> None:
        assert _score_systems(["payments", "auth"]) > _score_systems(["payments"])

    def test_caps_at_1_0(self) -> None:
        assert _score_systems(["a", "b", "c", "d", "e"]) <= 1.0


class TestScoreRationale:
    def test_empty_rationale_returns_low_score(self) -> None:
        assert _score_rationale([]) < 0.3

    def test_whitespace_only_returns_low_score(self) -> None:
        assert _score_rationale(["   ", ""]) < 0.3

    def test_substantive_rationale_boosts_score(self) -> None:
        assert _score_rationale(["Scale ceiling at 10M txn/day"]) > _score_rationale([])

    def test_two_rationale_points_higher_than_one(self) -> None:
        r1 = _score_rationale(["Reason A"])
        r2 = _score_rationale(["Reason A", "Reason B"])
        assert r2 > r1

    def test_caps_at_1_0(self) -> None:
        assert _score_rationale(["a" * 10] * 10) <= 1.0


class TestScoreContentLength:
    def test_very_short_content_returns_low_score(self) -> None:
        assert _score_content_length("ok") < 0.3

    def test_optimal_length_returns_high_score(self) -> None:
        # ~200 chars is peak
        content = "A" * 200
        assert _score_content_length(content) >= 0.9

    def test_very_long_content_returns_lower_score_than_optimal(self) -> None:
        optimal = _score_content_length("A" * 200)
        very_long = _score_content_length("A" * 3000)
        assert very_long < optimal

    def test_empty_content_returns_low_score(self) -> None:
        assert _score_content_length("") < 0.3

    def test_all_scores_in_range(self) -> None:
        for length in [0, 10, 50, 100, 200, 500, 1000, 2000, 5000]:
            score = _score_content_length("A" * length)
            assert 0.0 <= score <= 1.0, f"score out of range for length {length}: {score}"


class TestScoreSupersedes:
    def test_replaces_set_returns_1_0(self) -> None:
        assert _score_supersedes("prev-id-001") == 1.0

    def test_replaces_none_returns_0_0(self) -> None:
        assert _score_supersedes(None) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Band classification
# ─────────────────────────────────────────────────────────────────────────────


class TestImportanceBand:
    def test_below_discard(self) -> None:
        assert _importance_band(IMPORTANCE_DISCARD - 0.01) == "discard"

    def test_at_discard_threshold(self) -> None:
        assert _importance_band(IMPORTANCE_DISCARD) == "compress"

    def test_compress_range(self) -> None:
        assert _importance_band((IMPORTANCE_DISCARD + IMPORTANCE_COMPRESS) / 2) == "compress"

    def test_at_compress_threshold(self) -> None:
        assert _importance_band(IMPORTANCE_COMPRESS) == "full"

    def test_full_range(self) -> None:
        assert _importance_band((IMPORTANCE_COMPRESS + IMPORTANCE_FULL) / 2) == "full"

    def test_full_notify_range(self) -> None:
        assert _importance_band(IMPORTANCE_FULL + 0.01) == "full_notify"

    def test_at_1_0(self) -> None:
        assert _importance_band(1.0) == "full_notify"


# ─────────────────────────────────────────────────────────────────────────────
# ImportanceScorer.score()
# ─────────────────────────────────────────────────────────────────────────────


class TestImportanceScorerScore:
    def test_score_mutates_importance_score(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        assert decision.importance_score == 0.0
        scorer.score(decision)
        assert decision.importance_score > 0.0

    def test_score_returns_same_decision_object(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        result = scorer.score(decision)
        assert result is decision

    def test_score_is_in_valid_range(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        scorer.score(decision)
        assert 0.0 <= decision.importance_score <= 1.0

    def test_decision_scores_higher_than_update(self) -> None:
        scorer = ImportanceScorer()
        d1 = _make_decision(event_type="decision")
        d2 = _make_decision(event_type="update")
        scorer.score(d1)
        scorer.score(d2)
        assert d1.importance_score > d2.importance_score

    def test_more_persons_yields_higher_score(self) -> None:
        scorer = ImportanceScorer()
        d1 = _make_decision(made_by=["alice@"])
        d2 = _make_decision(made_by=["alice@", "bob@", "carol@"])
        scorer.score(d1)
        scorer.score(d2)
        assert d2.importance_score >= d1.importance_score

    def test_with_rationale_scores_higher_than_without(self) -> None:
        scorer = ImportanceScorer()
        d_with = _make_decision(rationale=["Scale ceiling at 10M txn/day"])
        d_without = _make_decision(rationale=[])
        scorer.score(d_with)
        scorer.score(d_without)
        assert d_with.importance_score > d_without.importance_score

    def test_superseding_decision_scores_higher(self) -> None:
        scorer = ImportanceScorer()
        d_supersedes = _make_decision(replaces="old-decision-id")
        d_new = _make_decision(replaces=None)
        scorer.score(d_supersedes)
        scorer.score(d_new)
        assert d_supersedes.importance_score > d_new.importance_score


# ─────────────────────────────────────────────────────────────────────────────
# ImportanceScorer.score_with_breakdown()
# ─────────────────────────────────────────────────────────────────────────────


class TestImportanceScorerBreakdown:
    def test_does_not_mutate_decision(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        original_score = decision.importance_score
        scorer.score_with_breakdown(decision)
        assert decision.importance_score == original_score

    def test_breakdown_components_sum_approximately_to_total(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        breakdown = scorer.score_with_breakdown(decision)

        reconstructed = (
            0.35 * breakdown.event_type_score
            + 0.20 * breakdown.person_score
            + 0.20 * breakdown.system_score
            + 0.15 * breakdown.rationale_score
            + 0.05 * breakdown.content_length_score
            + 0.05 * breakdown.supersedes_score
        )
        assert abs(reconstructed - breakdown.total) < 0.001

    def test_band_matches_total(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        breakdown = scorer.score_with_breakdown(decision)
        assert breakdown.band == _importance_band(breakdown.total)

    def test_all_components_in_range(self) -> None:
        scorer = ImportanceScorer()
        decision = _make_decision()
        bd = scorer.score_with_breakdown(decision)
        for component in [
            bd.event_type_score,
            bd.person_score,
            bd.system_score,
            bd.rationale_score,
            bd.content_length_score,
            bd.supersedes_score,
            bd.total,
        ]:
            assert 0.0 <= component <= 1.0
