"""OpenTelemetry initialisation for processor service."""

from __future__ import annotations

import logging

from .constants import OTEL_ENABLED, OTEL_ENDPOINT, OTEL_SERVICE_NAME


logger = logging.getLogger(__name__)


def setup_otel():
    """Initialise OTel TracerProvider if ``OTEL_ENABLED=true``.

    Returns:
        A tracer instance, or ``None`` when OTel is disabled or unavailable.
    """
    if not OTEL_ENABLED:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={"service.name": OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(
            "otel_initialized",
            extra={"endpoint": OTEL_ENDPOINT, "service": OTEL_SERVICE_NAME},
        )
        return trace.get_tracer(OTEL_SERVICE_NAME)
    except Exception as exc:
        logger.warning("otel_init_failed", extra={"error": str(exc)})
        return None
