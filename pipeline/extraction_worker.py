"""Kafka worker: raw connector events to scored graph writes."""

from __future__ import annotations

import json
import os
import signal
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from pydantic import ValidationError

from extraction.decision_extractor import DecisionExtractor
from graph.writer import GraphWriter
from scoring.importance import ImportanceScorer
from scoring.trust_scorer import TrustScorer, is_writable
from shared.models import RawEvent

log = structlog.get_logger(__name__)

RAW_TOPICS = [
    "cortex.raw.slack.messages",
    "cortex.raw.github.events",
    "cortex.raw.jira.events",
]
EXTRACTED_TOPIC = "cortex.extracted.decisions"
CONSUMER_GROUP = "cortex-extraction-worker"


def _delivery_callback(err: Any, msg: Any) -> None:
    if err:
        log.error("kafka.delivery.failed", topic=msg.topic(), error=str(err))
    else:
        log.debug(
            "kafka.delivery.success",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


class ExtractionWorker:
    """Consumes raw events, extracts decisions, scores, and writes to Neo4j."""

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        group_id: str = CONSUMER_GROUP,
    ) -> None:
        servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        )
        self._consumer = Consumer(
            {
                "bootstrap.servers": servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._producer = Producer(
            {
                "bootstrap.servers": servers,
                "acks": "all",
                "enable.idempotence": True,
            }
        )
        self._extractor = DecisionExtractor()
        self._importance = ImportanceScorer()
        self._trust = TrustScorer()
        self._writer = GraphWriter()
        self._processed: set[str] = set()
        self._running = True
        log.info("pipeline.worker.initialized", topics=RAW_TOPICS, group_id=group_id)

    def stop(self) -> None:
        self._running = False

    def process_raw_event(self, raw_event: RawEvent) -> str | None:
        """Run extraction, scoring, and graph write for one raw event."""
        if raw_event.event_id in self._processed:
            log.debug("pipeline.event.duplicate", event_id=raw_event.event_id)
            return None

        decision = self._extractor.extract(raw_event)
        if decision is None:
            self._processed.add(raw_event.event_id)
            return None

        self._importance.score(decision)
        self._trust.score(decision)

        if not is_writable(decision.trust_score):
            log.info(
                "pipeline.event.quarantined",
                event_id=decision.event_id,
                trust_score=decision.trust_score,
            )
            self._processed.add(raw_event.event_id)
            return None

        try:
            event_id = self._writer.write(decision)
        except ValueError as exc:
            log.info(
                "pipeline.event.discarded",
                event_id=decision.event_id,
                reason=str(exc),
            )
            self._processed.add(raw_event.event_id)
            return None

        payload = decision.model_dump_json().encode("utf-8")
        self._producer.produce(
            topic=EXTRACTED_TOPIC,
            key=decision.event_id.encode(),
            value=payload,
            callback=_delivery_callback,
        )
        self._producer.poll(0)
        self._processed.add(raw_event.event_id)
        return event_id

    def _handle_message(self, message: Any) -> None:
        if message.error():
            if message.error().code() == KafkaError._PARTITION_EOF:
                return
            raise KafkaException(message.error())

        try:
            payload = json.loads(message.value().decode("utf-8"))
            raw_event = RawEvent.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
            log.error("pipeline.message.invalid", error=str(exc))
            return

        self.process_raw_event(raw_event)

    def run_once(self, timeout: float = 1.0) -> bool:
        """Poll Kafka once. Returns False when no message was processed."""
        message = self._consumer.poll(timeout)
        if message is None:
            return False
        self._handle_message(message)
        self._consumer.commit(asynchronous=False)
        return True

    def run(self) -> None:
        """Blocking worker loop."""
        self._consumer.subscribe(RAW_TOPICS)
        log.info("pipeline.worker.started", topics=RAW_TOPICS)
        while self._running:
            try:
                self.run_once(timeout=1.0)
            except KafkaException as exc:
                log.error("pipeline.worker.kafka_error", error=str(exc))
        self.close()

    def close(self) -> None:
        self._producer.flush(10.0)
        self._consumer.close()
        self._writer.close()
        log.info("pipeline.worker.closed")


def main() -> None:
    worker = ExtractionWorker()

    def _handle_signal(*_args: object) -> None:
        worker.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    worker.run()


if __name__ == "__main__":
    main()
