from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge

# Provider metrics
provider_requests_total = Counter(
    "provider_requests_total", "Total requests by provider", ["provider"]
)
provider_latency_ms = Histogram(
    "provider_latency_ms", "Latency per provider in ms", buckets=(50,100,200,400,800,1600,3200,6400), labelnames=("provider",)
)

# Generation tokens (simple counters; wire up if providers expose usage)
generation_tokens_total = Counter(
    "generation_tokens_total", "Total tokens by provider and role", ["provider","role"]
)

# Oracle costs
oracle_calls_total = Counter(
    "oracle_calls_total", "Total oracle calls", ["engine"]
)
oracle_cost_usd_total = Counter(
    "oracle_cost_usd_total", "Total oracle cost USD", ["engine"]
)

# LoRA evaluation score (latest gauge)
lora_eval_score = Gauge(
    "lora_eval_score", "LoRA evaluation score", ["model","task"]
)

# Ingest backlog gauge (to be wired by watcher if queue exists)
ingest_backlog_gauge = Gauge(
    "ingest_backlog_gauge", "Ingest backlog length"
)