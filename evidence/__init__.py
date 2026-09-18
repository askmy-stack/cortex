"""Evidence graph package — adapters, authority, writer, explain."""

from evidence.adapters import (
    claim_evidence_bundle,
    decision_to_claim,
    decision_to_evidence,
    evidence_graph_enabled,
)
from evidence.authority import compare_authority, score_for_class

__all__ = [
    "claim_evidence_bundle",
    "compare_authority",
    "decision_to_claim",
    "decision_to_evidence",
    "evidence_graph_enabled",
    "score_for_class",
]
