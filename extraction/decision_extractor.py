"""Decision extractor — transforms RawEvents into structured DecisionEvents.

Two-stage pipeline:
  1. Classification: is this a decision, exception, rationale, update, or noise?
  2. Extraction: if classified, extract into DecisionEvent schema.

Backend selection via EXTRACTION_BACKEND env var:
  "openai"  → GPT-4o function calling (production)
  "ollama"  → local Ollama model (development, zero API cost)

Decision: D-009 — GPT-4o production, Ollama Gemma development.
Decision: D-003 — LLM extracts structure, never scores trust.

Architecture: Layer 2 — Extraction Engine.
Kafka consumer topic: cortex.raw.slack.messages (and future sources)
Kafka producer topic: cortex.extracted.decisions
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any

import structlog
from openai import OpenAI
from pydantic import ValidationError

from shared.models import (
    CONFIDENCE_DISCARD,
    CONFIDENCE_REVIEW,
    DecisionEvent,
    EventType,
    Provenance,
    RawEvent,
)

log = structlog.get_logger(__name__)

EXTRACTOR_VERSION = "0.1.0"

# ─────────────────────────────────────────────────────────────────────────────
# OpenAI function schema — enforces structured DecisionEvent extraction
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_FUNCTION = {
    "name": "extract_decision_event",
    "description": (
        "Extract a structured organizational decision event from a message. "
        "Only call this function if a real decision, exception, rationale, or update was made. "
        "Do NOT extract from casual conversation, questions, or informal discussion."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": ["decision", "exception", "rationale", "update", "escalation"],
                "description": "Classification of the organizational event",
            },
            "content": {
                "type": "string",
                "description": "Clean one-to-two sentence summary of the decision",
            },
            "made_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of people who made or approved this decision (names or usernames)",
            },
            "affects": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Systems, services, teams, or components affected by this decision",
            },
            "rationale": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reasons or justifications explicitly stated for this decision",
            },
            "replaces": {
                "type": ["string", "null"],
                "description": "Description of the previous decision this supersedes, if any",
            },
            "triggered_by": {
                "type": ["string", "null"],
                "description": "Incident ID, ticket ID, or event that triggered this decision",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Your confidence (0–1) that this message contains a real organizational decision. "
                    "Be conservative: casual mentions score < 0.4, clear decisions score > 0.7."
                ),
            },
        },
        "required": ["event_type", "content", "confidence"],
    },
}

_SYSTEM_PROMPT = """You are an organizational memory extractor for Cortex.

Your job: identify if a message contains an organizational decision, exception, rationale, or update.
If it does, extract it into the provided schema.

Guidelines:
- Extract only when a real, concrete decision was made — not proposals, questions, or casual mentions.
- "We decided to migrate to CockroachDB" → extract (decision, confidence ~0.9)
- "Maybe we should look at CockroachDB?" → do NOT extract (confidence < 0.4)
- "We had an incident where the payments service timed out" → extract as exception
- "The reason we chose Redis is it's faster for this access pattern" → extract as rationale
- Be conservative. False positives pollute the knowledge graph permanently.
- Do not hallucinate people, systems, or rationale not present in the message.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Extraction result cache (content-hash deduplication)
# Decision: D-009 — cache by content hash, never call API twice for same content
# ─────────────────────────────────────────────────────────────────────────────

_extraction_cache: dict[str, DecisionEvent | None] = {}


def _content_hash(content: str) -> str:
    """SHA-256 hash of content for cache key."""
    return hashlib.sha256(content.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Backend implementations
# ─────────────────────────────────────────────────────────────────────────────


def _call_openai(content: str, model: str, client: OpenAI) -> dict[str, Any] | None:
    """Call GPT-4o with function calling to extract a DecisionEvent.

    Args:
        content: The message text to extract from.
        model: OpenAI model name (e.g. 'gpt-4o').
        client: Initialised OpenAI client.

    Returns:
        Extracted dict or None if model determined no decision present.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        tools=[{"type": "function", "function": _EXTRACTION_FUNCTION}],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=1024,
    )

    choice = response.choices[0]
    tool_calls = choice.message.tool_calls

    if not tool_calls:
        return None

    return json.loads(tool_calls[0].function.arguments)


def _call_ollama(content: str, model: str, base_url: str) -> dict[str, Any] | None:
    """Call local Ollama model to extract a DecisionEvent.

    Uses the OpenAI-compatible Ollama endpoint. Falls back to JSON mode
    since not all Ollama models support tool calling.

    Args:
        content: The message text to extract from.
        model: Ollama model name (e.g. 'gemma2:latest').
        base_url: Ollama server base URL.

    Returns:
        Extracted dict or None if no decision detected.
    """
    client = OpenAI(api_key="ollama", base_url=f"{base_url}/v1")

    schema_description = json.dumps(_EXTRACTION_FUNCTION["parameters"], indent=2)
    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Output ONLY valid JSON matching this schema (or empty JSON {{}} if not a decision):\n"
        f"{schema_description}\n\n"
        f"Message:\n{content}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content or "{}"

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("ollama.response.invalid_json", raw_response=raw[:200])
        return None

    return parsed if parsed.get("content") else None


# ─────────────────────────────────────────────────────────────────────────────
# Main extractor
# ─────────────────────────────────────────────────────────────────────────────


class DecisionExtractor:
    """Extracts structured DecisionEvents from RawEvents.

    Backend is selected via EXTRACTION_BACKEND env var:
      "openai" → GPT-4o (production)
      "ollama" → local model (development)

    Usage:
        extractor = DecisionExtractor()
        decision = extractor.extract(raw_event)
        if decision is not None:
            # decision.extraction_confidence >= CONFIDENCE_DISCARD
            # route to review queue if < CONFIDENCE_REVIEW
            pass
    """

    def __init__(self) -> None:
        """Initialise the extractor from environment variables."""
        self.backend = os.environ.get("EXTRACTION_BACKEND", "ollama").lower()
        self.extractor_model = ""

        if self.backend == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY must be set for openai extraction backend")
            self.extractor_model = os.environ.get("OPENAI_MODEL", "gpt-4o")
            self._client: OpenAI = OpenAI(api_key=api_key)
        elif self.backend == "ollama":
            self._ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self.extractor_model = os.environ.get("OLLAMA_MODEL", "gemma2:latest")
            self._client = None  # type: ignore[assignment]
        else:
            raise ValueError(
                f"Unknown EXTRACTION_BACKEND: {self.backend!r}. "
                "Expected 'openai' or 'ollama'."
            )

        log.info(
            "extractor.initialized",
            backend=self.backend,
            model=self.extractor_model,
            version=EXTRACTOR_VERSION,
        )

    def extract(self, raw_event: RawEvent) -> DecisionEvent | None:
        """Extract a DecisionEvent from a RawEvent.

        Pipeline:
          1. Check content-hash cache (avoid duplicate API calls).
          2. Call LLM backend for classification + extraction.
          3. If confidence < CONFIDENCE_DISCARD: return None (discard).
          4. Build DecisionEvent with provenance chain.

        Args:
            raw_event: The normalised connector event to extract from.

        Returns:
            DecisionEvent if a decision was found and confidence >= CONFIDENCE_DISCARD.
            None if no decision was detected or confidence too low.
        """
        content = raw_event.content
        cache_key = _content_hash(content)

        if cache_key in _extraction_cache:
            log.debug("extractor.cache_hit", event_id=raw_event.event_id)
            return _extraction_cache[cache_key]

        log.info(
            "extractor.processing",
            event_id=raw_event.event_id,
            source=raw_event.source,
            content_length=len(content),
            backend=self.backend,
        )

        try:
            extracted = self._call_backend(content)
        except Exception as exc:
            log.error(
                "extractor.backend_error",
                event_id=raw_event.event_id,
                backend=self.backend,
                error=str(exc),
            )
            _extraction_cache[cache_key] = None
            return None

        if extracted is None:
            log.info("extractor.no_decision", event_id=raw_event.event_id)
            _extraction_cache[cache_key] = None
            return None

        confidence = float(extracted.get("confidence", 0.0))

        if confidence < CONFIDENCE_DISCARD:
            log.info(
                "extractor.discarded",
                event_id=raw_event.event_id,
                confidence=confidence,
                threshold=CONFIDENCE_DISCARD,
            )
            _extraction_cache[cache_key] = None
            return None

        provenance = Provenance(
            source=raw_event.source,
            channel=raw_event.channel,
            original_timestamp=raw_event.timestamp,
            extractor_version=EXTRACTOR_VERSION,
            extractor_model=self.extractor_model,
            verified_by=[],
            raw_event_id=raw_event.event_id,
        )

        try:
            decision = DecisionEvent(
                source_raw_event_id=raw_event.event_id,
                workspace_id=raw_event.workspace_id,
                event_type=extracted.get("event_type", "decision"),  # type: ignore[arg-type]
                content=extracted["content"],
                made_by=extracted.get("made_by", []),
                affects=extracted.get("affects", []),
                rationale=extracted.get("rationale", []),
                replaces=extracted.get("replaces"),
                triggered_by=extracted.get("triggered_by"),
                extraction_confidence=confidence,
                provenance=provenance,
            )
        except (ValidationError, KeyError) as exc:
            log.error(
                "extractor.schema_error",
                event_id=raw_event.event_id,
                error=str(exc),
                extracted=extracted,
            )
            _extraction_cache[cache_key] = None
            return None

        confidence_band = (
            "review_queue" if confidence < CONFIDENCE_REVIEW else "pass_to_scorer"
        )
        log.info(
            "extractor.decision_extracted",
            event_id=raw_event.event_id,
            decision_id=decision.event_id,
            event_type=decision.event_type,
            confidence=confidence,
            confidence_band=confidence_band,
            affects_count=len(decision.affects),
            made_by_count=len(decision.made_by),
        )

        _extraction_cache[cache_key] = decision
        return decision

    def _call_backend(self, content: str) -> dict[str, Any] | None:
        """Dispatch to the configured LLM backend.

        Args:
            content: Message text to analyse.

        Returns:
            Extracted dict or None.
        """
        if self.backend == "openai":
            return _call_openai(content, self.extractor_model, self._client)
        return _call_ollama(content, self.extractor_model, self._ollama_base_url)
