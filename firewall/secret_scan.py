"""Secret / PII pattern scan before durable memory writes."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}")),
    ("private_key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("password_assignment", re.compile(r"(?i)password\s*[:=]\s*\S+")),
]


@dataclass
class ScanFinding:
    kind: str
    span: str


def scan_secrets(text: str) -> list[ScanFinding]:
    """Return secret-like findings in text."""
    findings: list[ScanFinding] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            findings.append(ScanFinding(kind=kind, span=match.group(0)[:40]))
    return findings


def redact(text: str) -> str:
    """Redact secret-like spans."""
    out = text or ""
    for _, pattern in _PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out
