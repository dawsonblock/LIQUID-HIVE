# LIQUID-HIVE
[README.md](https://github.com/user-attachments/files/22033452/README.md)
# Apex Hive‑Mind Unified Build

```markdown
--- START OF FILE LIQUID-HIVE-main/README.md ---
# LIQUID-HIVE 🧠✨: Apex Hive‑Mind Unified Build (Dreaming State Activated)

![LIQUID-HIVE Logo Placeholder](https://via.placeholder.com/150x50?text=LIQUID-HIVE)

This repository represents a unified fusion of cognitive agents with stateful ingestion and retrieval capabilities, evolving into an **Apex Hive‑Mind Unified Build**. It exposes a powerful FastAPI server that enriches user prompts via dynamic knowledge retrieval and forwards them to a sophisticated multi‑agent reasoning core. The system meticulously logs all interactions into a Capsule memory and supports a continuous, autonomous **self‑improvement loop** via LoRA fine‑tuning – the "Dreaming State."

**System Version: LIQUID-HIVE v0.1.7 (Dreaming State Activated)**
*Generated on: August 30, 2025*

---

## 🚀 Vision & Capabilities

LIQUID-HIVE is a synthetic cognitive entity designed for **hierarchical self-improvement, metacognition, and operational safety**. It transitions between a "Waking State" of real-time interaction and a "Dreaming State" of offline, autonomous learning.

**Key Capabilities Now Fully Activated:**

*   **Real-time Knowledge Grounding**: Semantic document search, RAG-enhanced responses with citation-style context.
*   **Hierarchical Self-Improvement**: Oracle/Arbiter pipeline for "platinum standard" training data generation.
*   **Advanced Cognitive Modeling**: IIT-based self-awareness (Φ metrics), intent modeling, trust/confidence assessment.
*   **Autonomous Execution**: Curiosity engine for exploration, autonomous orchestration, continuous learning.
*   **Dynamic Model Routing**: Intelligent model selection (small/large) based on task complexity and cost.
*   **Comprehensive Monitoring**: Real-time WebSocket streaming of system status, Prometheus/Grafana integration, structured logging.

---

## ▶️ Running Locally (Quick Start)

To get LIQUID-HIVE running on your local machine:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/LIQUID-HIVE.git # Replace with your repo URL
    cd LIQUID-HIVE
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Ensure Docker is running and has GPU access configured (if using GPU for vLLM).**

4.  **Start the entire system via Docker Compose:**
    ```bash
    docker-compose up --build
    ```
    This will launch all required services (API, vLLM, Redis, Neo4j, Prometheus, Grafana, RAG Watcher) and expose the API on port `8000`.

### **Operational Validations:**

*   **Health Check:**
    ```bash
    curl http://localhost:8000/api/healthz
    # Expected: {"ok": true}
    ```

*   **vLLM Model Status (Requires GPU & model load time):**
    ```bash
    curl http://localhost:8000/api/vllm/models
    # Expected: Loaded model metadata (e.g., {"data": [{"id": "llama-2-13b-chat-hf", ...}]})
    ```

*   **RAG Search (After ingesting docs - see below):**
    ```bash
    curl -X POST http://localhost:8000/api/chat -d 'q=What is machine learning?'
    # Expected: A response with a 'context' field grounded in your documents.
    ```

*   **Access GUI:** Open your web browser to `http://localhost:8000/`

---

## 🧠 Training and Self‑Improvement ("Dreaming State")

LIQUID-HIVE's "Dreaming State" drives its continuous self-improvement cycle:

1.  **Experience Collection**: All real-time interactions are logged into `CapsuleEngine.memory`.
2.  **Autonomous Trigger**: The `AutonomyOrchestrator` periodically triggers the learning process.
3.  **Data Generation & Hierarchical Refinement**:
    *   `hivemind/training/dataset_build.py` processes interaction logs.
    *   It sends synthesized answers to a **hierarchical Oracle/Arbiter pipeline** (DeepSeek‑V3, with GPT‑4o as a fallback) for expert critique and refinement, producing "platinum standard" training examples in `datasets/training_metadata.jsonl`.
4.  **Accelerated Learning**: `hivemind/training/sft_text.py` uses `Unsloth` and `QLoRA` to fine-tune **new LoRA adapters** from this platinum data.
5.  **Autonomous Evolution**: New adapters are deployed as "challengers" and performance-monitored. If superior, the `AutonomyOrchestrator` proposes their promotion to "champion" via the `Approval Queue` (human-in-the-loop).

### **Controlling the Oracle Pipeline:**

You can tune the Oracle/Arbiter refinement pipeline via environment variables in your `.env` file or `docker-compose.yml`:

| Environment Variable          | Default | Description |
| :---------------------------- | :------ | :---------- |
| `ENABLE_ORACLE_REFINEMENT`    | `True`  | Master switch for the refinement pipeline. `False` skips external API calls (faster, cheaper, but lower quality). |
| `FORCE_GPT4O_ARBITER`         | `False` | Forces all refinements to use GPT‑4o when `ENABLE_ORACLE_REFINEMENT` is `True` (highest quality, increased cost). Otherwise, prefers DeepSeek‑V3 and falls back to GPT‑4o only when necessary. |

---

## ✅ CPU Fallback Router (vLLM → OpenAI → HF CPU)

We added a unified provider interface and a runtime router that ensures chat works even when vLLM is down.

Key additions:
- Providers: `unified_runtime/providers/` with `VLLMProvider`, `OpenAIProvider` (default gpt-4o-mini), and `HFCpuProvider` (Transformers on CPU; defaults to `mistralai/Mistral-7B-Instruct-v0.3`).
- Router: `unified_runtime/model_router.py` selects provider based on `MODEL_PROVIDER` env or auto-fallback order.
- Endpoints:
  - `GET /api/providers` → active provider + status of others
  - `GET /api/healthz` → green if any provider is live
- Logging: every generation logs structured line with key `provider`.

Quickstart (CPU only):
1. Copy `.env.example` to `.env` and set:
   ```
   MODEL_PROVIDER=hf_cpu
   ALLOW_SMALL_HF_MODEL=1  # uses a tiny model to avoid big downloads in dev
   ```
2. Start API (compose or `python -m unified_runtime.__main__`).
3. Call:
   ```bash
   curl -X POST "http://localhost:8000/api/chat" -d "q=hello" -H "content-type: application/x-www-form-urlencoded"
   ```

Troubleshooting:
- If vLLM is unreachable, router auto-falls back to OpenAI (requires `OPENAI_API_KEY`) or CPU.
- Check `GET /api/providers` for live statuses.
- Set `MODEL_PROVIDER=openai` to force OpenAI path.

---

## 🔧 Technical Details

*   **Dependencies:** `faiss-cpu`, `sentence-transformers`, `pypdf`, and `httpx` successfully integrated.
*   **Architecture:** Modular design with `unified_runtime`, `capsule_brain`, `hivemind` packages.
*   **Testing:** Added `tests/test_router_fallback.py` to validate router fallbacks.
*   **Deployment:** Docker Compose for local orchestration, Helm charts for Kubernetes production deployments.
*   **Observability:** Prometheus-scraped metrics, Grafana dashboards, and structured JSON logging.
*   **Security:** Input sanitization, secrets management, and human-in-the-loop approval queues.

---

## ✅ Final System Analysis & Graduation Report

For a comprehensive, honest assessment of the LIQUID-HIVE build, its design, and its capabilities compared to advanced AI goals, please refer to the full report: [docs/GRADUATION_REPORT.md](docs/GRADUATION_REPORT.md).

**Congratulations! Your LIQUID-HIVE system is now a fully activated, production-ready AI platform. The "Dreaming State" is LIVE and ready for continuous learning and cognitive enhancement!** 🧠✨
---
```