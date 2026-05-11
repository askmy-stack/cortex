"""Tests for extraction/decision_extractor.py.

Tests cover:
- Extraction from 20 representative Slack message samples
- Confidence threshold enforcement (discard < 0.4, review 0.4–0.7, pass > 0.7)
- Content-hash cache deduplication (no duplicate LLM calls)
- Provenance chain populated correctly
- Extractor initialisation (backend selection)
- LLM backend calls (mocked — no real API calls in tests)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from extraction.decision_extractor import (
    DecisionExtractor,
    _content_hash,
    _extraction_cache,
)
from shared.models import (
    CONFIDENCE_DISCARD,
    CONFIDENCE_REVIEW,
    DecisionEvent,
    RawEvent,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE_ID = "test-workspace"


def _make_raw_event(content: str, source: str = "slack") -> RawEvent:
    """Build a minimal RawEvent for testing."""
    return RawEvent(
        source=source,  # type: ignore[arg-type]
        source_id="C-test:1715000000.000",
        workspace_id=WORKSPACE_ID,
        event_type=f"{source}:message",
        content=content,
        author="U12345",
        channel="C-engineering",
        timestamp=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
    )


def _mock_extracted(
    confidence: float = 0.9,
    event_type: str = "decision",
    content: str = "We decided to migrate payments to CockroachDB.",
    made_by: list[str] | None = None,
    affects: list[str] | None = None,
    rationale: list[str] | None = None,
) -> dict[str, Any]:
    """Build a mock LLM extraction result."""
    return {
        "event_type": event_type,
        "content": content,
        "confidence": confidence,
        "made_by": made_by or ["priya@company.com"],
        "affects": affects or ["payments-service"],
        "rationale": rationale or ["Scale ceiling at 10M txn/day"],
        "replaces": None,
        "triggered_by": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Extractor initialisation
# ─────────────────────────────────────────────────────────────────────────────


class TestDecisionExtractorInit:
    def test_ollama_backend_initialised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        extractor = DecisionExtractor()
        assert extractor.backend == "ollama"

    def test_openai_backend_raises_without_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            DecisionExtractor()

    def test_openai_backend_initialised_with_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        extractor = DecisionExtractor()
        assert extractor.backend == "openai"
        assert extractor.extractor_model == "gpt-4o"

    def test_unknown_backend_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "anthropic")
        with pytest.raises(ValueError, match="Unknown EXTRACTION_BACKEND"):
            DecisionExtractor()


# ─────────────────────────────────────────────────────────────────────────────
# Extraction — decision detected
# ─────────────────────────────────────────────────────────────────────────────


class TestDecisionExtracted:
    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        _extraction_cache.clear()

    @patch.object(DecisionExtractor, "_call_backend")
    def test_returns_decision_event_on_high_confidence(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=0.9)

        extractor = DecisionExtractor()
        raw = _make_raw_event("We decided to migrate payments to CockroachDB.")
        result = extractor.extract(raw)

        assert result is not None
        assert isinstance(result, DecisionEvent)
        assert result.extraction_confidence == 0.9
        assert result.event_type == "decision"

    @patch.object(DecisionExtractor, "_call_backend")
    def test_decision_event_content_matches_extraction(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(
            content="Migrate payments service to CockroachDB.",
            affects=["payments-service"],
            made_by=["priya@", "dan@"],
        )
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("..."))

        assert result is not None
        assert "payments-service" in result.affects
        assert "priya@" in result.made_by

    @patch.object(DecisionExtractor, "_call_backend")
    def test_provenance_chain_populated(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted()
        extractor = DecisionExtractor()
        raw = _make_raw_event("Decision message")
        result = extractor.extract(raw)

        assert result is not None
        assert result.provenance.source == "slack"
        assert result.provenance.raw_event_id == raw.event_id
        assert result.provenance.extractor_version == "0.1.0"

    @patch.object(DecisionExtractor, "_call_backend")
    def test_workspace_id_propagated(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted()
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Some message"))

        assert result is not None
        assert result.workspace_id == WORKSPACE_ID

    @patch.object(DecisionExtractor, "_call_backend")
    def test_exception_event_type_extracted(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(
            event_type="exception",
            content="Auth service times out when JWT expiry < 60s",
            confidence=0.85,
        )
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Auth service times out ..."))

        assert result is not None
        assert result.event_type == "exception"

    @patch.object(DecisionExtractor, "_call_backend")
    def test_rationale_event_type_extracted(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(
            event_type="rationale",
            content="Redis chosen for sub-50ms latency requirements",
            confidence=0.8,
        )
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Redis was chosen because..."))

        assert result is not None
        assert result.event_type == "rationale"


# ─────────────────────────────────────────────────────────────────────────────
# Confidence threshold enforcement
# ─────────────────────────────────────────────────────────────────────────────


class TestConfidenceThresholds:
    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        _extraction_cache.clear()

    @patch.object(DecisionExtractor, "_call_backend")
    def test_below_discard_threshold_returns_none(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=0.2)
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Maybe we should look at CockroachDB"))
        assert result is None

    @patch.object(DecisionExtractor, "_call_backend")
    def test_at_discard_threshold_returns_none(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=CONFIDENCE_DISCARD - 0.001)
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Uncertain message"))
        assert result is None

    @patch.object(DecisionExtractor, "_call_backend")
    def test_review_queue_range_returns_decision_event(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=0.55)
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Probably decided something"))
        # DecisionEvent is returned — caller routes to review queue based on confidence
        assert result is not None
        assert result.extraction_confidence == 0.55

    @patch.object(DecisionExtractor, "_call_backend")
    def test_none_from_backend_returns_none(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = None
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Just a casual chat message"))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Cache deduplication
# ─────────────────────────────────────────────────────────────────────────────


class TestCacheDeduplication:
    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        _extraction_cache.clear()

    @patch.object(DecisionExtractor, "_call_backend")
    def test_same_content_only_calls_backend_once(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted()
        extractor = DecisionExtractor()

        content = "We decided to use Kafka as our event bus."
        r1 = extractor.extract(_make_raw_event(content))
        r2 = extractor.extract(_make_raw_event(content))

        assert mock_call.call_count == 1
        assert r1 is r2

    @patch.object(DecisionExtractor, "_call_backend")
    def test_different_content_calls_backend_twice(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted()
        extractor = DecisionExtractor()

        extractor.extract(_make_raw_event("Decision A: use Kafka"))
        extractor.extract(_make_raw_event("Decision B: use Redis"))

        assert mock_call.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Backend error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestBackendErrorHandling:
    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        _extraction_cache.clear()

    @patch.object(DecisionExtractor, "_call_backend")
    def test_backend_exception_returns_none(
        self, mock_call: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.side_effect = RuntimeError("Connection refused")
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event("Decision message"))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# 20 representative Slack message samples
# Testing that clearly non-decision messages return None when backend says low confidence
# ─────────────────────────────────────────────────────────────────────────────


DECISION_MESSAGES = [
    "We've decided to move the auth service to OAuth2. Priya and Dan signed off.",
    "Architecture decision: all inter-service communication goes through Kafka only.",
    "Resolved: migrate payments service to CockroachDB. Triggered by incident #247.",
    "We're deprecating the old REST endpoint on May 30. No exceptions.",
    "Decision: Redis for session cache, 24h TTL. Max memory 512MB.",
    "The team agreed: TypeScript only for new services going forward.",
    "Finalized: Qdrant replaces Pinecone for vector search in the memory layer.",
    "We're adopting LangGraph for all agent orchestration. No AutoGen.",
    "Neo4j chosen over Amazon Neptune due to cost and self-host flexibility.",
    "Exception noted: auth service fails when JWT expiry < 60 seconds.",
]

NON_DECISION_MESSAGES = [
    "Hey, has anyone looked at the logs from last night?",
    "Maybe we should consider CockroachDB at some point?",
    "lol the deploy just failed again",
    "Can someone review my PR?",
    "Lunch at 12?",
    "I'm not sure what we should do here",
    "Interesting, I hadn't thought of that",
    "The build is taking forever today",
    "just wondering if anyone tested this path",
    "great work everyone!",
]


class TestMessageSamples:
    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        _extraction_cache.clear()

    @patch.object(DecisionExtractor, "_call_backend")
    @pytest.mark.parametrize("text", DECISION_MESSAGES)
    def test_decision_messages_extracted_with_high_confidence(
        self, mock_call: MagicMock, text: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=0.85, content=text)
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event(text))
        assert result is not None, f"Expected decision extracted from: {text!r}"
        assert result.extraction_confidence >= CONFIDENCE_DISCARD

    @patch.object(DecisionExtractor, "_call_backend")
    @pytest.mark.parametrize("text", NON_DECISION_MESSAGES)
    def test_non_decision_messages_discarded(
        self, mock_call: MagicMock, text: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXTRACTION_BACKEND", "ollama")
        mock_call.return_value = _mock_extracted(confidence=0.15, content=text)
        extractor = DecisionExtractor()
        result = extractor.extract(_make_raw_event(text))
        assert result is None, f"Expected None (non-decision) for: {text!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Content hash utility
# ─────────────────────────────────────────────────────────────────────────────


class TestContentHash:
    def test_same_content_same_hash(self) -> None:
        h1 = _content_hash("hello")
        h2 = _content_hash("hello")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        assert _content_hash("hello") != _content_hash("world")

    def test_hash_is_hex_string(self) -> None:
        h = _content_hash("test")
        assert all(c in "0123456789abcdef" for c in h)
