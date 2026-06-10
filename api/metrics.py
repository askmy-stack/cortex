"""Prometheus metrics for the Cortex API.

Exposed at ``GET /metrics`` for Prometheus scrape (see infrastructure/docker/prometheus.yml).
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "cortex_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_LATENCY = Histogram(
    "cortex_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

QUERY_REQUESTS = Counter(
    "cortex_query_requests_total",
    "Total /query requests",
    ["status"],
)

QUERY_LATENCY = Histogram(
    "cortex_query_duration_seconds",
    "/query handler latency in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def record_http_request(*, method: str, endpoint: str, status: int, duration_s: float) -> None:
    """Record generic HTTP request metrics."""
    HTTP_REQUESTS.labels(method, endpoint, str(status)).inc()
    HTTP_LATENCY.labels(method, endpoint).observe(duration_s)


def record_query(*, status: str, duration_s: float) -> None:
    """Record /query-specific metrics."""
    QUERY_REQUESTS.labels(status).inc()
    QUERY_LATENCY.observe(duration_s)


def render_metrics() -> tuple[bytes, str]:
    """Return Prometheus exposition payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
