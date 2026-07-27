"""Explicit memory capture — publish manual events into the Kafka pipeline."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime

import structlog
from confluent_kafka import KafkaException, Producer
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import RolesDep
from shared.models import RawEvent

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/remember", tags=["memory"])

KAFKA_TOPIC = "cortex.raw.manual.events"

# Module-level lazy singleton — one Producer for the process lifetime.
# Matches connector pattern (SlackKafkaProducer keeps a long-lived client).
_producer_lock = threading.Lock()
_producer_instance: Producer | None = None


class RememberRequest(BaseModel):
    workspace_id: str = Field(description="Workspace to store memory in")
    content: str = Field(min_length=10, max_length=8000, description="Decision or context text")
    author: str = Field(default="api-user", description="Who is submitting this memory")
    channel: str = Field(default="api", description="Logical channel (team, project, etc.)")
    affects: list[str] = Field(
        default_factory=list,
        description="System ids this memory relates to (hint for extractor)",
    )


class RememberResponse(BaseModel):
    status: str
    event_id: str
    topic: str


def _producer() -> Producer:
    """Return the shared Kafka producer, creating it on first use."""
    global _producer_instance
    if _producer_instance is not None:
        return _producer_instance
    with _producer_lock:
        if _producer_instance is None:
            servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            _producer_instance = Producer(
                {
                    "bootstrap.servers": servers,
                    "acks": "all",
                    "enable.idempotence": True,
                }
            )
        return _producer_instance


def _reset_producer_for_tests() -> None:
    """Clear the singleton between tests (test helper only)."""
    global _producer_instance
    with _producer_lock:
        _producer_instance = None


@router.post(
    "",
    response_model=RememberResponse,
    summary="Submit explicit organizational memory",
)
async def remember(request: RememberRequest, roles: RolesDep) -> RememberResponse:
    """Publish a manual RawEvent to Kafka for extraction and graph write.

    Same pipeline as connector webhooks: importance → trust → Neo4j.
    """
    raw = RawEvent(
        source="manual",
        source_id=f"manual:{request.workspace_id}:{datetime.now(UTC).timestamp()}",
        workspace_id=request.workspace_id,
        event_type="cortex:remember",
        content=request.content,
        author=request.author,
        channel=request.channel,
        timestamp=datetime.now(UTC),
        metadata={"affects_hint": request.affects, "origin": "api_remember"},
    )
    try:
        producer = _producer()
        producer.produce(
            topic=KAFKA_TOPIC,
            key=f"{raw.workspace_id}:{raw.event_id}".encode(),
            value=raw.model_dump_json().encode("utf-8"),
        )
        remaining = producer.flush(10.0)
        if remaining > 0:
            raise KafkaException("Kafka flush incomplete")
    except KafkaException as exc:
        log.error("remember.kafka_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to publish memory event to Kafka",
        ) from exc

    log.info(
        "remember.published",
        event_id=raw.event_id,
        workspace_id=request.workspace_id,
        caller_roles=roles,
    )
    return RememberResponse(status="queued", event_id=raw.event_id, topic=KAFKA_TOPIC)
