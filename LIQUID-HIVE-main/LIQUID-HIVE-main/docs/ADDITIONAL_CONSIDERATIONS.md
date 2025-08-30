# Additional Considerations (Synergy & Mastery Protocol)

This document captures operational, security, observability, migration, and testing considerations that accompany the recent fixes and enhancements to LIQUID‑HIVE.

## 1) Security & Safety
- Input sanitization:
  - /api/chat now sanitizes q via capsule_brain.security.input_sanitizer.sanitize_input. If you require rich Markdown or code blocks, ensure the sanitizer configuration preserves expected formatting while still stripping prompt‑injection vectors.
  - Consider server‑side rate limiting and abuse detection (per‑IP, per‑token burst control) to mitigate prompt abuse and DoS.
- Secrets & credentials:
  - docker-compose now uses NEO4J_AUTH=${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-change_this_password}. Set NEO4J_USER and NEO4J_PASSWORD via secrets manager or environment for all non‑local deployments.
  - Prefer capsule_brain or cloud secrets managers to inject credentials at runtime; avoid committing .env files.
- Autonomy safety gates:
  - CuriosityEngine and any open‑ended workflows are human‑in‑the‑loop via the Approval Queue. Maintain this invariant for production; do not bypass approvals.
- Data privacy:
  - Consider redacting PII within logs/memory (e.g., email, phone, keys) before storage. Add a redact_sensitive() hook in engine.add_memory paths if required by compliance.

## 2) Observability & Metrics
- Grafana metrics:
  - Dashboard panels updated to cb_* metrics (cb_request_latency_seconds_bucket, cb_http_requests_total, cb_tokens_total). Ensure Prometheus scrape config and exporter labels produce these metrics.
  - Removed non‑existent panels (planner_queue_depth, overseer_*). Reintroduce only when instrumented.
- Alerts:
  - Consider adding SLO alerts: p95 latency > threshold for X minutes, 5xx ratio spike, unexpected token spend spikes.
- Cognitive Map visibility:
  - AutonomyOrchestrator writes Skill nodes to Neo4j (if configured) or a JSON snapshot at runs_dir/cognitive_map.json. Build a Grafana panel or GUI tab to surface confidence trends per domain.

## 3) Migration & Backward Compatibility
- backend/ removal:
  - The legacy backend/ directory has been removed. The canonical entrypoint is unified_runtime (python -m unified_runtime.__main__). Update any external supervisor/docker configs that referenced backend/server.py.
- Foundational adapter path centralization:
  - Settings.foundational_adapter_path controls the initial champion adapter. Override via environment (FOUNDATIONAL_ADAPTER_PATH) or secrets manager if you relocate adapters.
- Routing to small/large models:
  - StrategySelector outputs chosen_model alias (Courier/Master). Ensure vLLM (or equivalent) small/large endpoints are configured in secrets/env (vllm_endpoint_small / vllm_endpoint_large) before enabling MODEL_ROUTING_ENABLED.

## 4) Performance & Cost Management
- Economic routing:
  - ResourceEstimator predicts tokens to bias routing. Tune COST_PER_1K_TOKENS_* in Settings if you want tighter cost control.
- Online learning (LoRAX):
  - If lorax_endpoint is provided, AutonomyOrchestrator streams refined examples for immediate LoRA updates. Gate with traffic sampling and add rollback procedures (see below) to avoid drift.
- Rate caps & quotas:
  - Add per‑tenant quotas and concurrency limits at the gateway to prevent runaway compute costs on “Master” model selection.

## 5) Rollback & Recovery
- Model routing:
  - If small/large backends become unstable, set MODEL_ROUTING_ENABLED=False to route to the default roles object.
- LoRAX online updates:
  - If model quality regresses, disable lorax_endpoint and revert to a known good adapter via AdapterDeploymentManager promote flow, or reset settings.text_adapter_path.
- Grafana dashboard:
  - Export current dashboards before changes; you can re‑import a prior JSON to rollback visualizations.

## 6) Testing Strategy
- Backend:
  - Unit tests for sanitize_input behavior (allowlist vs blocklist cases).
  - Integration tests for chat error handling branches (mock httpx.RequestError, KeyError scenarios).
  - Contract tests for StrategySelector decision outputs (strategy, model, chosen_model) with mocked estimator/cognitive map inputs.
- Frontend:
  - ChatPanel tests now include a vision path when image is attached. Consider adding error path tests and ensuring selector_reason and chosen_model are surfaced in UI if needed.
- E2E:
  - docker-compose up and smoke test /api/healthz, /api/chat, /api/approvals, Grafana dashboards loading, Prometheus scrape.

## 7) Deployment & Configuration
- docker-compose:
  - Ensure NEO4J_USER/NEO4J_PASSWORD are set in local .env for developer machines.
- Helm/Kubernetes:
  - Mirror the NEO4J_AUTH pattern in values and secrets; mount adapters PVC; expose Prometheus and Grafana via ingress; ensure /api ingress path maps to API service.
- Storage:
  - Persist runs_dir, adapters_dir, rag_index via volumes; ensure correct permissions.

## 8) Data & Licensing
- Datasets:
  - Verify licenses for Open‑Orca/SlimOrca and Teknium/OpenHermes‑2.5 for your deployment context. Provide attribution if required.
- Memory retention:
  - Define retention and purging for runs/ and curiosity artifacts, especially in regulated environments.

## 9) Roadmap Hooks
- Future planner metrics (planner_queue_depth) can be added after instrumenting planner queue gauges.
- Overseer approvals/rejections can be exported as counters when Approval Queue actions are persisted.
- Advanced estimator: Optionally incorporate small embedding models to refine token prediction or topic complexity classification.