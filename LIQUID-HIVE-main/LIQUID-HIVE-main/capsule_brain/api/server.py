import asyncio, logging, os
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from capsule_brain.core.capsule_engine import CapsuleEngine
from capsule_brain.observability.metrics import router as metrics_router, MetricsMiddleware

log = logging.getLogger(__name__)
app = FastAPI(title="Capsule Brain Supreme AGI", version="1.0.1")

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Metrics
app.add_middleware(MetricsMiddleware)
app.include_router(metrics_router)

engine: CapsuleEngine | None = None

@app.on_event("startup")
async def on_startup():
    global engine
    engine = CapsuleEngine()
    await engine.start_background_tasks()
    log.info("Engine started.")

@app.on_event("shutdown")
async def on_shutdown():
    if engine:
        await engine.shutdown()

@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True}

@app.get("/ready")
async def ready() -> Dict[str, Any]:
    return {"ready": engine is not None}

@app.get("/state/summary")
async def state_summary() -> Dict[str, Any]:
    if not engine: raise HTTPException(status_code=503, detail="engine not ready")
    return engine.get_state_summary()

@app.post("/ask")
async def ask(q: str) -> Dict[str, Any]:
    if not engine: raise HTTPException(status_code=503, detail="engine not ready")
    engine.add_memory("user", q)
    context, system_prompt = engine.belief_state_manager.synthesize_context_for_llm()
    return {"ack": True, "context": context, "system": system_prompt}

@app.post("/graph/edge")
async def add_edge(source: str, target: str, relation: str = "related_to") -> Dict[str, Any]:
    if not engine: raise HTTPException(status_code=503, detail="engine not ready")
    engine.add_graph_edge(source, target, relation)
    return {"ok": True, "graph": {"nodes": engine.knowledge_graph.number_of_nodes(), "edges": engine.knowledge_graph.number_of_edges()}}
