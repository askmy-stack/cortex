"""Action risk levels and policy thresholds."""

from __future__ import annotations

from shared.v2_models import ActionRisk

# Minimum action_confidence required to ACT, by risk.
ACT_THRESHOLDS: dict[ActionRisk, float] = {
    "READ_ONLY": 0.40,
    "LOW_RISK_WRITE": 0.55,
    "REVERSIBLE_WRITE": 0.70,
    "HIGH_IMPACT_WRITE": 0.85,
    "IRREVERSIBLE": 0.92,
    "PRIVILEGED": 0.95,
}

VERIFY_BAND = 0.15  # if within this of threshold → VERIFY instead of ACT


def threshold_for(risk: ActionRisk | str) -> float:
    """Return ACT threshold for a risk level."""
    return float(ACT_THRESHOLDS.get(risk, 0.85))  # type: ignore[arg-type]


def roles_may_act(roles: list[str], risk: ActionRisk | str) -> bool:
    """Authorization check outside the LLM."""
    role_set = {r.lower() for r in roles}
    if risk in {"HIGH_IMPACT_WRITE", "IRREVERSIBLE", "PRIVILEGED"}:
        return bool(role_set & {"admin", "operator", "sre", "lead"})
    if risk in {"REVERSIBLE_WRITE", "LOW_RISK_WRITE"}:
        return bool(role_set & {"admin", "operator", "sre", "lead", "engineer", "authenticated"})
    return "authenticated" in role_set or bool(role_set)
