"""Contradiction detection — flags conflicting decisions before memory poisons agents.

Architecture: Layer 4 — Intelligence.
Decision: contradictions surfaced to human review; new decision may move to under_review.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from confluent_kafka import KafkaException, Producer
from neo4j import Driver, GraphDatabase

from graph.rbac import serialize_access_policy
from shared.models import DecisionEvent

log = structlog.get_logger(__name__)

_DEFAULT_ACCESS_POLICY: dict[str, str | list[str] | bool] = {
    "roles": ["authenticated"],
    "deny": [],
    "classification": "internal",
    "gdpr_subject": False,
}

_CONFLICT_TOPIC = "cortex.intelligence.contradictions"
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "we",
        "is",
        "are",
        "was",
        "be",
        "as",
        "at",
        "it",
        "this",
        "that",
        "with",
        "not",
    }
)


@dataclass(frozen=True)
class ConflictCandidate:
    """A candidate conflicting decision already in the graph."""

    decision_id: str
    content: str
    overlap_score: float


def token_set(text: str) -> set[str]:
    """Lowercased content tokens minus trivial stopwords."""
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text)
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def jaccard_similarity(a: str, b: str) -> float:
    """Token Jaccard similarity in [0, 1]."""
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def negation_mismatch(a: str, b: str) -> bool:
    """Heuristic: one text negates the other's core claim (very rough)."""
    la, lb = a.lower(), b.lower()
    neg = (" not ", " no ", "won't", "never", "avoid", "don't", "do not ")
    pos = (" will ", " use ", " adopt ", " migrate ", " choose ", " pick ")
    a_neg = any(n in la for n in neg)
    b_neg = any(n in lb for n in neg)
    a_pos = any(p in la for p in pos)
    b_pos = any(p in lb for p in pos)
    return (a_neg and b_pos and not b_neg) or (b_neg and a_pos and not a_neg)


class ContradictionDetector:
    """Finds overlapping decisions on shared systems and lexical mismatch."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        bootstrap_servers: str | None = None,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "cortex_local")
        self._driver: Driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )
        servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        )
        self._producer: Producer | None = None
        if os.environ.get("CORTEX_CONTRADICTION_KAFKA", "true").lower() in {
            "1",
            "true",
            "yes",
        }:
            self._producer = Producer({"bootstrap.servers": servers, "acks": "all"})

    def close(self) -> None:
        self._driver.close()
        if self._producer is not None:
            self._producer.flush(10.0)

    def find_candidates(self, decision: DecisionEvent) -> list[ConflictCandidate]:
        """Return other active decisions that share affected systems."""
        cypher = """
        MATCH (d:Decision {id: $id})-[:AFFECTS]->(s:System)
        MATCH (other:Decision)-[:AFFECTS]->(s)
        WHERE other.id <> $id
          AND other.workspace_id = $workspace_id
          AND other.status IN ['active', 'under_review']
        RETURN DISTINCT other.id AS oid, other.content AS content
        """
        candidates: list[ConflictCandidate] = []
        with self._driver.session() as session:
            result = session.run(
                cypher,
                id=decision.event_id,
                workspace_id=decision.workspace_id,
            )
            for record in result:
                oid = record["oid"]
                content = record["content"] or ""
                score = jaccard_similarity(decision.content, content)
                if negation_mismatch(decision.content, content):
                    score = max(score, 0.55)
                if score >= 0.28:
                    candidates.append(
                        ConflictCandidate(
                            decision_id=str(oid),
                            content=str(content),
                            overlap_score=round(score, 4),
                        )
                    )
        candidates.sort(key=lambda c: c.overlap_score, reverse=True)
        return candidates[:5]

    def persist_and_notify(
        self,
        decision: DecisionEvent,
        candidates: list[ConflictCandidate],
    ) -> str | None:
        """Create Contradiction node, link decisions, optionally publish to Kafka."""
        if not candidates:
            return None

        top = candidates[0]
        cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{decision.event_id}:{top.decision_id}"))

        cypher = """
        MATCH (new:Decision {id: $new_id})
        MATCH (old:Decision {id: $old_id})
        MERGE (c:Contradiction {id: $cid})
        ON CREATE SET
            c.workspace_id = $workspace_id,
            c.status = 'pending',
            c.score = $score,
            c.explanation = $explanation,
            c.detected_at = datetime(),
            c.access_policy = $access_policy
        MERGE (c)-[:INVOLVES_NEW]->(new)
        MERGE (c)-[:INVOLVES_PRIOR]->(old)
        SET new.status = CASE WHEN $score >= 0.5 THEN 'under_review' ELSE new.status END
        RETURN c.id AS id
        """

        explanation = (
            f"Lexical overlap {top.overlap_score:.2f} on shared systems; "
            f"compare with decision {top.decision_id}"
        )

        with self._driver.session() as session:
            session.run(
                cypher,
                new_id=decision.event_id,
                old_id=top.decision_id,
                cid=cid,
                workspace_id=decision.workspace_id,
                score=top.overlap_score,
                explanation=explanation,
                access_policy=serialize_access_policy(_DEFAULT_ACCESS_POLICY),
            )

        payload = {
            "contradiction_id": cid,
            "workspace_id": decision.workspace_id,
            "new_decision_id": decision.event_id,
            "existing_decision_id": top.decision_id,
            "score": top.overlap_score,
            "explanation": explanation,
        }
        if self._producer is not None:
            try:
                self._producer.produce(
                    topic=_CONFLICT_TOPIC,
                    key=cid.encode(),
                    value=json.dumps(payload).encode("utf-8"),
                )
                self._producer.poll(0)
            except KafkaException as exc:
                log.error("contradiction.kafka_failed", error=str(exc))

        log.warning(
            "contradiction.detected",
            contradiction_id=cid,
            new_decision_id=decision.event_id,
            existing_decision_id=top.decision_id,
            score=top.overlap_score,
        )
        return cid
