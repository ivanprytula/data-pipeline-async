"""Processor service constants."""

from __future__ import annotations

import os


BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BROKER_URL", "redpanda:29092")
TOPIC: str = "records.events"
TOPIC_DLQ: str = "records.events.dlq"
GROUP_ID: str = "processor-group"
MAX_RETRIES: int = 3

OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "processor")

# Redpanda leader-election retry parameters
_RETRY_SLEEP_SECONDS: int = 5
_RETRY_MAX_ATTEMPTS: int = 12  # 60 s total
