"""LLM-backed CMVK verifiers for production high-stakes writes.

Three independent verifier personas call the same OpenAI or Ollama backend with
different review lenses. Majority vote (2/3) is applied by CrossModelVerificationKernel.

Decision: D-006 — CMVK majority voting for importance > 0.8.
Backend: CORTEX_CMVK_BACKEND=openai|ollama (heuristic is default in cmvk.py).
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
from openai import OpenAI

from scoring.cmvk import DecisionVerifier, VerifierVote
from shared.models import DecisionEvent

log = structlog.get_logger(__name__)

_VERIFICATION_FUNCTION = {
    "name": "verify_decision_event",
    "description": (
        "Approve or reject a high-stakes extracted decision before it is stored "
        "in the organizational memory graph."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "approved": {
                "type": "boolean",
                "description": "True only when the decision passes this verifier's checks.",
            },
            "rationale": {
                "type": "string",
                "description": "One sentence explaining the approve/reject outcome.",
            },
        },
        "required": ["approved", "rationale"],
    },
}

_VERIFIER_PROMPTS: dict[str, str] = {
    "cmvk-llm-structure": """You are CMVK verifier A — structural completeness.

Review the extracted DecisionEvent JSON. Approve only when:
- content is a concrete organizational decision/exception/rationale/update (not noise)
- made_by is present when the text implies authors or approvers
- affects or rationale is populated when the decision references systems or reasons

Reject vague summaries, questions, or incomplete extractions.""",
    "cmvk-llm-provenance": """You are CMVK verifier B — extraction quality and provenance.

Review the extracted DecisionEvent JSON. Approve only when:
- extraction_confidence is plausible for the content (not inflated)
- fields appear grounded in the message (no obvious hallucinated people/systems)
- source/channel metadata is consistent with a real connector event

Reject when the extraction looks over-confident or fabricated.""",
    "cmvk-llm-stakes": """You are CMVK verifier C — high-stakes justification.

This decision has importance_score > 0.8. Approve only when:
- the event materially affects architecture, policy, security, or operations
- it is actionable organizational memory (not casual chat or weak status noise)
- storing it permanently in a knowledge graph is justified

Reject low-stakes chatter incorrectly marked as high importance.""",
}

_OLLAMA_EXAMPLE = '{"approved": true, "rationale": "Concrete decision with authors and affected systems."}'


def decision_payload(decision: DecisionEvent) -> dict[str, Any]:
    """Serialize fields relevant to CMVK review (no scores that bias verifiers)."""
    return {
        "event_type": decision.event_type,
        "content": decision.content,
        "made_by": decision.made_by,
        "affects": decision.affects,
        "rationale": decision.rationale,
        "replaces": decision.replaces,
        "triggered_by": decision.triggered_by,
        "extraction_confidence": decision.extraction_confidence,
        "importance_score": decision.importance_score,
        "status": decision.status,
        "provenance": {
            "source": decision.provenance.source,
            "channel": decision.provenance.channel,
            "extractor_model": decision.provenance.extractor_model,
            "extractor_version": decision.provenance.extractor_version,
        },
    }


def _parse_verdict(raw: str) -> dict[str, Any] | None:
    """Parse LLM JSON verdict; tolerate fenced code blocks."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return None
    if "approved" not in parsed:
        return None
    return parsed


def _call_openai_verify(
    client: OpenAI,
    model: str,
    system_prompt: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Call OpenAI with function calling for a structured verdict."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Review this extracted DecisionEvent and return your verdict.\n\n"
                    f"{json.dumps(payload, indent=2)}"
                ),
            },
        ],
        tools=[{"type": "function", "function": _VERIFICATION_FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "verify_decision_event"}},
        temperature=0.0,
    )
    message = response.choices[0].message
    if not message.tool_calls:
        return None
    arguments = message.tool_calls[0].function.arguments
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return None


def _call_ollama_verify(
    base_url: str,
    model: str,
    system_prompt: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Call Ollama OpenAI-compatible API with JSON verdict output."""
    client = OpenAI(api_key="ollama", base_url=f"{base_url.rstrip('/')}/v1")
    prompt = (
        f"{system_prompt}\n\n"
        "Output ONLY a JSON object with fields: approved (boolean), rationale (string).\n"
        f"Example:\n{_OLLAMA_EXAMPLE}\n\n"
        f"DecisionEvent:\n{json.dumps(payload, indent=2)}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=256,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return _parse_verdict(raw)


class LLMDecisionVerifier:
    """Single LLM verifier with a fixed review lens."""

    def __init__(
        self,
        verifier_id: str,
        system_prompt: str,
        *,
        backend: str,
        model: str,
        ollama_base_url: str = "http://localhost:11434",
        client: OpenAI | None = None,
    ) -> None:
        self.verifier_id = verifier_id
        self._system_prompt = system_prompt
        self._backend = backend
        self._model = model
        self._ollama_base_url = ollama_base_url
        self._client = client

    def _openai_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set for openai CMVK backend")
        return OpenAI(api_key=api_key)

    def verify(self, decision: DecisionEvent) -> VerifierVote:
        """Return approve/reject verdict from the configured LLM backend."""
        payload = decision_payload(decision)
        try:
            if self._backend == "openai":
                result = _call_openai_verify(
                    self._openai_client(),
                    self._model,
                    self._system_prompt,
                    payload,
                )
            elif self._backend == "ollama":
                result = _call_ollama_verify(
                    self._ollama_base_url,
                    self._model,
                    self._system_prompt,
                    payload,
                )
            else:
                return VerifierVote(
                    self.verifier_id,
                    False,
                    f"unsupported backend: {self._backend}",
                )
        except Exception as exc:
            log.warning(
                "cmvk.llm.verifier_failed",
                verifier_id=self.verifier_id,
                error=str(exc),
            )
            return VerifierVote(self.verifier_id, False, f"llm error: {exc}")

        if result is None:
            return VerifierVote(self.verifier_id, False, "verifier returned no result")

        approved = bool(result.get("approved"))
        rationale = str(result.get("rationale", "")).strip()
        if not rationale:
            rationale = "approved" if approved else "rejected"
        return VerifierVote(self.verifier_id, approved, rationale[:500])


def validate_cmvk_backend(backend: str | None = None) -> None:
    """Fail fast when LLM CMVK is enabled but the backend is unreachable.

    Without this check, every verifier returns ``approved=False`` on API errors,
    CMVK majority fails, and high-stakes writes are silently quarantined.
    """
    resolved = (backend or os.environ.get("CORTEX_CMVK_BACKEND", "heuristic")).lower()
    if resolved == "heuristic":
        return
    if resolved not in {"openai", "ollama"}:
        return

    if resolved == "openai":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise ValueError(
                "CORTEX_CMVK_BACKEND=openai but OPENAI_API_KEY is unset. "
                "Set OPENAI_API_KEY or use CORTEX_CMVK_BACKEND=heuristic for local demo."
            )
        return

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        import urllib.error
        import urllib.request

        urllib.request.urlopen(f"{base_url}/api/tags", timeout=3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError(
            f"CORTEX_CMVK_BACKEND=ollama but Ollama is unreachable at {base_url}: {exc}. "
            "Start Ollama or set CORTEX_CMVK_BACKEND=heuristic."
        ) from exc


def build_llm_verifiers(backend: str) -> list[DecisionVerifier]:
    """Construct three independent LLM verifiers for the given backend."""
    validate_cmvk_backend(backend)
    if backend == "openai":
        model = os.environ.get("CORTEX_CMVK_OPENAI_MODEL", "gpt-4o-mini")
        ollama_base_url = ""
    else:
        model = os.environ.get("CORTEX_CMVK_OLLAMA_MODEL") or os.environ.get(
            "OLLAMA_MODEL", "llama3.1:8b"
        )
        ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    verifiers: list[DecisionVerifier] = []
    for verifier_id, prompt in _VERIFIER_PROMPTS.items():
        verifiers.append(
            LLMDecisionVerifier(
                verifier_id,
                prompt,
                backend=backend,
                model=model,
                ollama_base_url=ollama_base_url,
            )
        )
    log.info(
        "cmvk.llm_verifiers_built",
        backend=backend,
        model=model,
        count=len(verifiers),
    )
    return verifiers
