"""Tests for scoring/cmvk_llm.py — LLM-backed CMVK verifiers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from scoring.cmvk import CrossModelVerificationKernel, build_default_verifiers
from scoring.cmvk_llm import (
    LLMDecisionVerifier,
    _call_openai_verify,
    build_llm_verifiers,
    decision_payload,
)
from shared.models import IMPORTANCE_FULL, DecisionEvent, Provenance

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _decision(**overrides: object) -> DecisionEvent:
    base = DecisionEvent(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="We decided to migrate payments to CockroachDB for scale.",
        made_by=["alice@company.com"],
        affects=["payments-service"],
        rationale=["Scale ceiling at 10M txn/day"],
        extraction_confidence=0.9,
        importance_score=IMPORTANCE_FULL + 0.05,
        provenance=Provenance(
            source="github",
            channel="payments",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-1",
        ),
        extracted_at=NOW,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_decision_payload_includes_review_fields() -> None:
    payload = decision_payload(_decision())
    assert payload["event_type"] == "decision"
    assert payload["provenance"]["source"] == "github"
    assert payload["importance_score"] > IMPORTANCE_FULL


def test_build_default_verifiers_heuristic_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORTEX_CMVK_BACKEND", raising=False)
    verifiers = build_default_verifiers()
    assert len(verifiers) == 3
    assert verifiers[0].verifier_id.startswith("cmvk-heuristic")


def test_build_default_verifiers_openai_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_CMVK_BACKEND", "openai")
    verifiers = build_default_verifiers()
    assert [v.verifier_id for v in verifiers] == [
        "cmvk-llm-structure",
        "cmvk-llm-provenance",
        "cmvk-llm-stakes",
    ]


def test_llm_verifier_approves_openai_response() -> None:
    mock_client = MagicMock()
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(
        {"approved": True, "rationale": "well-formed decision"}
    )
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(tool_calls=[tool_call]))
    ]
    verifier = LLMDecisionVerifier(
        "cmvk-llm-structure",
        "prompt",
        backend="openai",
        model="gpt-4o-mini",
        client=mock_client,
    )
    vote = verifier.verify(_decision())
    assert vote.approved
    assert vote.rationale == "well-formed decision"


def test_llm_verifier_rejects_on_api_error() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("rate limited")
    verifier = LLMDecisionVerifier(
        "cmvk-llm-structure",
        "prompt",
        backend="openai",
        model="gpt-4o-mini",
        client=mock_client,
    )
    vote = verifier.verify(_decision())
    assert not vote.approved
    assert "llm error" in vote.rationale


def test_call_openai_verify_parses_tool_arguments() -> None:
    mock_client = MagicMock()
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(
        {"approved": False, "rationale": "content too vague"}
    )
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(tool_calls=[tool_call]))
    ]
    result = _call_openai_verify(mock_client, "gpt-4o-mini", "prompt", {"content": "x"})
    assert result is not None
    assert result["approved"] is False


@patch("scoring.cmvk_llm._call_openai_verify")
def test_kernel_majority_with_llm_verifiers(
    mock_verify: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    mock_verify.side_effect = [
        {"approved": True, "rationale": "ok"},
        {"approved": True, "rationale": "ok"},
        {"approved": False, "rationale": "stakes too low"},
    ]
    kernel = CrossModelVerificationKernel(verifiers=build_llm_verifiers("openai"))
    result = kernel.verify(_decision())
    assert result.approved
    assert len(result.approved_verifier_ids) == 2
