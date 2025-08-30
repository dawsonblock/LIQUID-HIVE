# LIQUID-HIVE
[README.md](https://github.com/user-attachments/files/22033452/README.md)
# Apex Hive‑Mind Unified Build

This repository represents a unified fusion of the cognitive agents from
`hivemind2` with the stateful ingestion and retrieval capabilities of
`hivemind_book_pipeline`.  It exposes a single FastAPI server in
`unified_runtime/server.py` that enriches user prompts via retrieval and
forwards them to a dynamic multi‑agent reasoning core.  The system logs
all interactions into a Capsule memory and supports a self‑improvement
loop via LoRA fine‑tuning.

## Key Components

- **unified_runtime/** – the entry point for serving requests.  It contains
  the FastAPI application, the dynamic strategy selector and the context
  bridge.
- **capsule_brain/** – provides long‑term memory, knowledge graph and
  self‑analysis routines.
- **hivemind/** – contains the agent roles, judge logic, retrieval and
  training scripts.
- **prometheus/** and **grafana/** – metrics collection and dashboards.
- **docker-compose.yml** – orchestrates the unified runtime and all supporting
  services.  It now includes Redis (message bus), Neo4j (knowledge graph), and
  a vLLM server (text model API) alongside Prometheus and Grafana for
  observability.

## Running Locally

Install the dependencies:

```bash
pip install -r requirements.txt
```

Then start the services:

```bash
docker-compose up --build
```

This will launch all required services and expose the API on port 8000.  You can
query it via:

```bash
curl -X POST http://localhost:8000/api/chat -d 'q=What is the capital of France?'
```

Health check:

```bash
curl http://localhost:8000/api/healthz
```

Vision example (multipart):

```bash
curl -X POST "http://localhost:8000/api/vision" \
  -F "question=Describe this image" \
  -F "file=@/path/to/image.png" \
  -F "grounding_required=false"
```

## Training and Self‑Improvement

Use the scripts in `hivemind/training/` to build datasets from the run logs
stored in the `/data/runs` directory and fine‑tune LoRA adapters.  The
dataset builder now employs a *hierarchical Oracle and Arbiter* pipeline to
refine the system's synthesized answers before they are used for training.
During dataset construction the `Arbiter` consults a primary Oracle
(DeepSeek‑V3) to critique and improve synthesized answers.  If the output
fails structural or semantic validation the task is escalated to a
secondary, more powerful Arbiter (GPT‑4o).  The resulting
`final_platinum_answer` is used as the target output for SFT/DPO and the
metadata records which model corrected each example are written to
`datasets/training_metadata.jsonl`.

The fine‑tuned adapters can be deployed by updating the `adapter`
path in your configuration.  For example, after running the `/train`
endpoint to produce a new adapter the `AdapterDeploymentManager` will
register it as a challenger and route a fraction of requests to it for
A/B testing.

This repository should be treated as a starting point.  Additional work is
required to merge the Helm charts, fine‑tune configuration and deploy in
production.

### Controlling the Oracle Pipeline

The Oracle/Arbiter refinement pipeline can be tuned or disabled entirely
through environment variables exposed by ``hivemind.config.Settings``.  These
variables are read by the dataset builder at runtime and allow you to
balance cost, quality and speed without modifying the code.

| Environment Variable | Default | Description |
| --- | --- | --- |
| ``ENABLE_ORACLE_REFINEMENT`` | ``True`` | Master switch for the refinement pipeline.  When set to ``False`` the dataset builder will skip all external API calls and simply use the Judge's synthesized answer.  This mode is the fastest and cheapest, suitable for offline or rapid iterations. |
| ``FORCE_GPT4O_ARBITER`` | ``False`` | Forces all refinements to use GPT‑4o instead of DeepSeek‑V3 when ``ENABLE_ORACLE_REFINEMENT`` is ``True``.  This produces the highest quality training data at increased cost.  When ``False`` the system will prefer DeepSeek‑V3 and only fall back to GPT‑4o when necessary. |

These environment variables can be set in your ``.env`` file or passed
directly via your orchestration layer (e.g. docker-compose).  For example,
to run a fast, low‑cost training cycle you can disable refinement:

```bash
ENABLE_ORACLE_REFINEMENT=False python -m hivemind.training.dataset_build
```

To force all examples through GPT‑4o for a golden dataset:

```bash
ENABLE_ORACLE_REFINEMENT=True FORCE_GPT4O_ARBITER=True python -m hivemind.training.dataset_build
```

## Additional Considerations

See docs/ADDITIONAL_CONSIDERATIONS.md for security, observability, migration, performance, testing, and deployment guidance associated with the latest changes.

### Operational Considerations (Summary)
- Security: Input sanitization in /api/chat; keep Approval Queue; use secrets manager (no committed .env).
- Observability: cb_* metrics in Grafana; consider SLO alerts for p95 latency, 5xx, token spikes.
- Migration: backend/ removed; unified_runtime is the API entrypoint; foundational_adapter_path centralized.
- Performance/Cost: Economic routing via StrategySelector; cap “Master” usage; gate LoRAX streaming and add rollback.
- Testing: New vision test on ChatPanel; add backend tests for sanitize_input and error handling.

## Final System Analysis & Graduation Report
- Read the comprehensive, honest assessment here: docs/GRADUATION_REPORT.md