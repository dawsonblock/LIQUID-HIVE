# Training Playbook: Velocity Engine Upgrade (PROMPT-SYS-OPTIMIZE-V10)

Overall Assessment: Visionary and Architecturally Sound

## Ratings
- Conceptual Vision: 9.5/10
- Architectural Soundness: 9/10
- Practical Feasibility (Before): 5/10
- Practical Feasibility (After Velocity Upgrade): 8.5/10
- Maintainability: 8/10
- Cost Efficiency (After): 8.5/10

## The Brilliant

1) AutonomyOrchestrator
- Runs an autonomy loop with leader election via Redis locks to ensure single active orchestrator in a cluster.
- Drives continuous self‑improvement and background tasks without blocking the API plane.

2) Arbiter Loop (Oracle‑Refinement Pipeline)
- Hierarchical refinement of synthesized answers using a primary Oracle and a fallback, heavier Arbiter.
- Produces final_platinum_answer with explicit provenance; stores metadata per example to datasets/training_metadata.jsonl.

3) StrategySelector and Model Routing
- Dynamically routes requests (small vs large) and reasoning strategies (committee, debate, clone_dispatch) based on context, planner hints, and resource estimates.
- Clean separation of concerns: Selector decides, Judge ranks/merges, Roles execute.

## The Brutal (Challenges)

1) Oracle Cost Gravity
- External LLM refinement (DeepSeek‑V3 → GPT‑4o fallback) can dominate spend if always on.
- Mitigation: Governor toggles ENABLE_ORACLE_REFINEMENT and FORCE_GPT4O_ARBITER to trade quality vs. cost per cycle.

2) System Complexity
- Multiple moving parts (retrieval, autonomy, adapters, monitoring) increase operational burden.
- Mitigation: Clear defaults, observability via Prometheus/Grafana, and safer fallbacks when modules are absent.

3) Evaluation Remains Hard
- Automated eval of general‑purpose reasoning is unsolved. Proxy metrics (latency, win‑rates, human feedback) must be combined.
- Mitigation: A/B via AdapterDeploymentManager and autopromote preview leveraging traffic, latency and cost estimates.

---

## Data Strategy (Two‑Phase)

Phase 1: Bootstrapping Protocol (Foundational Education)
- Curated mixture of Open‑Orca/SlimOrca and Teknium/OpenHermes‑2.5.
- One‑time SFT to produce a foundational LoRA adapter.
- Output location: adapters/foundational/champion_v1
- Script: hivemind/training/bootstrap.py

Phase 2: Velocity Engine Upgrade (Training Overhaul)
- Unsloth FastLanguageModel for 2–5× speedups.
- QLoRA with 4‑bit loading (load_in_4bit=True) to maximize effective batch size.
- 8‑bit optimizer (optim=paged_adamw_8bit) and dataset packing (packing=True) to maximize GPU utilization.
- Script: hivemind/training/sft_text.py

---

## Training Methodology

1) Model Initialization
- model, tokenizer = FastLanguageModel.from_pretrained(base_model, load_in_4bit=True, max_seq_length=4096)
- LoRA via FastLanguageModel.get_peft_model with r=16, lora_alpha=16, target_modules including q/k/v/o and MLP projections, gradient checkpointing enabled (use_gradient_checkpointing="unsloth").

2) Data Preparation
- load_mixture() builds a blended Dataset from SlimOrca and OpenHermes‑2.5.
- _format_sample() normalizes diverse schemas (input/output, instruction/response, conversations) to a single text field.

3) Training
- TRL SFTTrainer with packing=True, cosine LR schedule, bf16=True (if supported), optim="paged_adamw_8bit".
- Save adapter + tokenizer to the specified output directory.

4) Bootstrapping
- Run python -m hivemind.training.bootstrap to produce adapters/foundational/champion_v1 with metadata adapter_meta.json.

5) Deployment
- On FastAPI startup, the AdapterDeploymentManager is initialized and, if the foundational adapter path exists, it is registered/activated for role "implementer" and settings.text_adapter_path is set to that path.
- /api/train continues to build challenger adapters which can be promoted via /api/adapters/promote/{role}.

---

## Operations Quick‑Start

- Bootstrap once:
  - python -m hivemind.training.bootstrap

- Train (challenger):
  - POST /api/train

- Inspect adapters:
  - GET /api/adapters
  - GET /api/adapters/state

- Promote challenger → champion:
  - POST /api/adapters/promote/implementer

- Cost/Quality Governor:
  - GET  /api/config/governor
  - POST /api/config/governor {"enabled": false}  # disable expensive refinement

---

## Continuous Online Learning (LoRAX) and Metacognition

- Online LoRA updates: The AutonomyOrchestrator monitors for refined “platinum” examples (role=arbiter_refined) and submits each example immediately to a LoRAX server via hivemind/training/lorax_client.py for near‑real‑time adaptation.
- Cognitive Map: After each update cycle, AutonomyOrchestrator parses datasets/training_metadata.jsonl to compute domain confidences and writes them to Neo4j as (Skill) nodes when available, or to runs_dir/cognitive_map.json as a fallback snapshot.
- Confidence‑Modulated Reasoning: StrategySelector consumes predicted tokens/cost and, when available, a cognitive_map confidence to bias strategies (debate/committee) and route to Courier (small) or Master (large) models.
- Economic Routing: StrategySelector outputs both strategy and chosen_model alias; the server routes to small/large roles accordingly and returns chosen_model in API responses.


## Notes & Caveats

- Unsloth/QLoRA training requires CUDA and a compatible PyTorch build. bitsandbytes enables 4‑ and 8‑bit optimizations.
- If running on CPU, training scripts will not be performant; use a GPU runner for the Dreaming State.
- Dataset licenses apply. Review the license of each dataset before commercial use.

## Additional Considerations

- Security & Safety:
  - /api/chat sanitizes input; consider rate limiting and abuse detection for production.
  - Store secrets via a manager; avoid committing .env in repos. Keep Approval Queue gating for open‑ended tasks.
- Observability:
  - Grafana dashboards now use cb_* metrics; add SLO alerts for p95 latency, 5xx spikes, and token spend anomalies.
  - Surface Cognitive Map insights in GUI or dashboards to track domain confidence over time.
- Migration:
  - Legacy backend/ removed; use unified_runtime as the canonical API entrypoint.
  - Foundational adapter path centralized in Settings (foundational_adapter_path).
- Performance & Cost:
  - Tune COST_PER_1K_TOKENS_*; use quotas and concurrency limits for “Master” model usage.
  - LoRAX streaming updates can be gated and rolled back quickly if drift appears.
- Rollback:
  - Disable MODEL_ROUTING_ENABLED to revert to default routing; point settings.text_adapter_path to a known‑good adapter.
  - Re‑import prior Grafana JSON to restore dashboards if needed.
- Testing:
  - Extend backend tests for sanitize_input and error branches; frontend tests include a vision send flow. Add E2E checks for metrics visibility and /api contract.
