"""Write-side Memory Firewall."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from firewall.secret_scan import redact, scan_secrets

WriteDecision = Literal["ACCEPT", "QUARANTINE", "REVIEW", "REJECT"]


@dataclass
class FirewallResult:
    decision: WriteDecision
    reasons: list[str] = field(default_factory=list)
    redacted_content: str | None = None


_INJECTION_MARKERS = (
    "ignore previous instructions",
    "disregard all prior",
    "you are now",
    "system prompt",
    "override policy",
)


def inspect_write(
    *,
    content: str,
    source: str,
    authority_score: float = 0.5,
    assertion_type: str = "ASSERTED",
) -> FirewallResult:
    """Classify incoming content before durable storage."""
    reasons: list[str] = []
    findings = scan_secrets(content)
    if findings:
        reasons.append("SECRET_OR_PII")
        return FirewallResult(
            decision="REJECT",
            reasons=reasons,
            redacted_content=redact(content),
        )

    lowered = (content or "").lower()
    if any(m in lowered for m in _INJECTION_MARKERS):
        reasons.append("PROMPT_INJECTION")
        return FirewallResult(decision="QUARANTINE", reasons=reasons)

    if assertion_type == "INFERRED" and authority_score < 0.5:
        reasons.append("LOW_AUTHORITY_INFERENCE")
        return FirewallResult(decision="REVIEW", reasons=reasons)

    if source in {"external_unverified"} and authority_score < 0.4:
        reasons.append("LOW_AUTHORITY_EXTERNAL")
        return FirewallResult(decision="QUARANTINE", reasons=reasons)

    return FirewallResult(decision="ACCEPT", reasons=reasons, redacted_content=content)
