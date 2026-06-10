#!/usr/bin/env python3
"""Pre-create Cortex Kafka topics so the pipeline worker starts cleanly."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from pipeline.extraction_worker import DLQ_TOPIC, EXTRACTED_TOPIC, RAW_TOPICS

TOPICS = [*RAW_TOPICS, EXTRACTED_TOPIC, DLQ_TOPIC]


def main() -> int:
    load_dotenv(_REPO / ".env")
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    try:
        from confluent_kafka.admin import AdminClient, NewTopic
    except ImportError:
        print("FAIL: confluent-kafka not installed", file=sys.stderr)
        return 1

    admin = AdminClient({"bootstrap.servers": bootstrap})
    existing = admin.list_topics(timeout=10).topics
    to_create = [
        NewTopic(topic, num_partitions=1, replication_factor=1)
        for topic in TOPICS
        if topic not in existing
    ]

    if not to_create:
        print(f"All {len(TOPICS)} Cortex topics already exist on {bootstrap}")
        return 0

    futures = admin.create_topics(to_create)
    for topic, future in futures.items():
        try:
            future.result()
            print(f"Created topic {topic}")
        except Exception as exc:  # noqa: BLE001 — CLI boundary
            if "TOPIC_ALREADY_EXISTS" in str(exc):
                print(f"Topic {topic} already exists")
            else:
                print(f"FAIL: {topic}: {exc}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
