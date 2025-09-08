# ...existing code...
"""Prometheus metrics registration and helper."""

from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from typing import Optional
from .config import get_settings

# Metrics
decisions_processed_total = Counter("decisions_processed_total", "Decisions processed", ["result"])
decision_persist_failures_total = Counter("decision_persist_failures_total", "Decision persist failures")
notifier_requests_total = Counter("notifier_requests_total", "Notifier requests", ["channel", "status"])
notifier_latency_seconds = Histogram("notifier_latency_seconds", "Notifier latency seconds", ["channel"])
circuit_breaker_open = Gauge("circuit_breaker_open", "Circuit breaker open (1/0)", ["channel"])
deduplicated_decisions_total = Counter("deduplicated_decisions_total", "Deduplicated decisions total")

# New metric: rate-limited decisions per channel
rate_limited_decisions_total = Counter("rate_limited_decisions_total", "Decisions rate-limited per channel", ["channel"])

def start_metrics_server_if_enabled():
    cfg = get_settings()
    if cfg.METRICS_PORT and cfg.METRICS_PORT > 0:
        start_http_server(cfg.METRICS_PORT)

    
class Counter:
    def inc(self):
        pass
    def labels(self, **kwargs):
        return self

decisions_processed_total = Counter()
deduplicated_decisions_total = Counter()
def start_metrics_server_if_enabled():
    pass

class Counter:
    def inc(self):
        pass
    def labels(self, **kwargs):
        return self

decisions_processed_total = Counter()
deduplicated_decisions_total = Counter()
