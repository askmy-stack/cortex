"""Memory Reliability Gate — decide ACT/VERIFY/ASK/ESCALATE/BLOCK."""

from __future__ import annotations

from typing import Any

import structlog

from reliability import reason_codes as rc
from reliability.confidence import action_confidence, memory_confidence_from_claims
from reliability.policies import roles_may_act, threshold_for, VERIFY_BAND
from shared.v2_models import ActionRisk, ReliabilityDecision, ReliabilityVerdict

log = structlog.get_logger(__name__)

_RISK_PENALTY: dict[str, float] = {
    "READ_ONLY": 0.0,
    "LOW_RISK_WRITE": 0.05,
    "REVERSIBLE_WRITE": 0.10,
    "HIGH_IMPACT_WRITE": 0.20,
    "IRREVERSIBLE": 0.30,
    "PRIVILEGED": 0.35,
}


class ReliabilityGate:
    """Policy-aware gate between retrieval and agent action."""

    def evaluate(
        self,
        *,
        workspace_id: str,
        query: str,
        candidate_action: dict[str, Any],
        claims: list[dict[str, Any]] | None = None,
        memories: list[dict[str, Any]] | None = None,
        caller_roles: list[str] | None = None,
        risk: ActionRisk | str | None = None,
    ) -> ReliabilityDecision:
        """Evaluate whether memory is reliable enough for the candidate action."""
        claims = claims or []
        memories = memories or []
        roles = caller_roles or ["authenticated"]
        action_risk: ActionRisk = (risk or candidate_action.get("risk") or "READ_ONLY")  # type: ignore[assignment]
        if action_risk not in _RISK_PENALTY:
            action_risk = "HIGH_IMPACT_WRITE"

        reasons: list[str] = []
        checks: list[str] = []

        mem_conf = memory_confidence_from_claims(claims) if claims else 0.0
        if memories and not claims:
            # Fallback: use decision trust/importance averages
            scores = [
                float(m.get("trust_score") or m.get("importance_score") or 0.0)
                for m in memories
            ]
            mem_conf = sum(scores) / len(scores) if scores else 0.0

        if mem_conf < 0.4:
            reasons.append(rc.LOW_MEMORY_CONFIDENCE)
        if not claims and not memories:
            reasons.append(rc.INSUFFICIENT_EVIDENCE)

        conflict = False
        for c in claims:
            if str(c.get("status")) == "QUARANTINED":
                reasons.append(rc.QUARANTINED_MEMORY)
            if str(c.get("status")) == "SUPERSEDED":
                reasons.append(rc.SUPERSEDED_MEMORY)
            if str(c.get("assertion_type")) == "INFERRED":
                reasons.append(rc.INFERRED_ONLY)
            if c.get("conflict"):
                conflict = True
                reasons.append(rc.HIGH_AUTHORITY_CONFLICT)

        # Heuristic: single low-authority claim
        if len(claims) == 1 and float(claims[0].get("confidence") or 0) < 0.7:
            reasons.append(rc.SINGLE_SOURCE_SUPPORT)

        # Stale procedure signal from action metadata
        if candidate_action.get("stale_procedure") or candidate_action.get("procedure_status") == "STALE":
            reasons.append(rc.STALE_PROCEDURE)
            checks.append("verify current procedure version")
        if candidate_action.get("active_migration"):
            reasons.append(rc.ACTIVE_MIGRATION)
            checks.append("confirm migration window with owner")

        auth_ok = roles_may_act(roles, action_risk)
        if not auth_ok:
            reasons.append(rc.ACTION_NOT_AUTHORIZED)

        conflict_penalty = 0.25 if conflict or rc.HIGH_AUTHORITY_CONFLICT in reasons else 0.0
        if rc.STALE_PROCEDURE in reasons:
            conflict_penalty += 0.15
        if rc.ACTIVE_MIGRATION in reasons:
            conflict_penalty += 0.20

        act_conf = action_confidence(
            memory_conf=mem_conf,
            risk_penalty=_RISK_PENALTY.get(action_risk, 0.2),
            conflict_penalty=conflict_penalty,
            auth_ok=auth_ok,
        )

        verdict = self._decide(
            action_risk=action_risk,
            mem_conf=mem_conf,
            act_conf=act_conf,
            reasons=reasons,
            auth_ok=auth_ok,
        )

        # Dedupe reasons preserving order
        seen: set[str] = set()
        uniq_reasons = []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                uniq_reasons.append(r)

        decision = ReliabilityDecision(
            workspace_id=workspace_id,
            query_id=None,
            candidate_action={"query": query, **candidate_action},
            memory_confidence=round(mem_conf, 4),
            action_confidence=round(act_conf, 4),
            risk=action_risk,
            decision=verdict,
            reason_codes=uniq_reasons,
            required_checks=checks,
        )
        log.info(
            "reliability_gate.evaluated",
            decision=verdict,
            risk=action_risk,
            memory_confidence=decision.memory_confidence,
            action_confidence=decision.action_confidence,
            reasons=uniq_reasons,
        )
        return decision

    @staticmethod
    def _decide(
        *,
        action_risk: ActionRisk,
        mem_conf: float,
        act_conf: float,
        reasons: list[str],
        auth_ok: bool,
    ) -> ReliabilityVerdict:
        if not auth_ok or rc.ACTION_NOT_AUTHORIZED in reasons:
            return "BLOCK"
        if rc.QUARANTINED_MEMORY in reasons or rc.ACTIVE_MIGRATION in reasons:
            return "BLOCK"
        if rc.INSUFFICIENT_EVIDENCE in reasons or mem_conf < 0.35:
            return "ASK"
        if rc.HIGH_AUTHORITY_CONFLICT in reasons:
            return "ESCALATE"
        thr = threshold_for(action_risk)
        if act_conf >= thr:
            return "ACT"
        if act_conf >= thr - VERIFY_BAND or rc.STALE_PROCEDURE in reasons:
            return "VERIFY"
        if act_conf < 0.35:
            return "ASK"
        return "ESCALATE"
