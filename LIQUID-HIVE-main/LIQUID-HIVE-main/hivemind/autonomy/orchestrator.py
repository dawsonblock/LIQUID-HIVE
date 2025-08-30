from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
from typing import Any, Dict, Optional

try:
    from ..training.lorax_client import LoRAXClient
except Exception:  # pragma: no cover
    LoRAXClient = None  # type: ignore


class AutonomyOrchestrator:
    """Lightweight autonomy loop for continuous learning and cognitive mapping.

    Responsibilities (condensed):
      - Watch for refined "platinum" examples and send to LoRAX server for online SFT
      - Maintain/update a Cognitive Map based on training metadata
    """

    def __init__(self, engine: Any, adapter_manager: Optional[Any], settings: Optional[Any]) -> None:
        self.engine = engine
        self.adapter_manager = adapter_manager
        self.settings = settings
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.base_dir = pathlib.Path(getattr(settings, "runs_dir", "/app/data"))
        self.datasets_dir = pathlib.Path("/app/datasets")

        # LoRAX client
        try:
            if LoRAXClient and settings is not None:
                self.lorax = LoRAXClient(getattr(settings, "lorax_endpoint", None), getattr(settings, "lorax_api_key", None))
            else:
                self.lorax = None
        except Exception:
            self.lorax = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="autonomy_orchestrator_loop")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._process_platinum_examples()
                await self._update_cognitive_map()
            except Exception:
                pass
            await asyncio.sleep(15)

    async def _process_platinum_examples(self) -> None:
        """Scan engine memory for refined platinum examples and submit online SFT."""
        try:
            events = []
            try:
                events = list(self.engine.memory)  # type: ignore
            except Exception:
                events = []
            for item in events[-50:]:
                if item.get("role") == "arbiter_refined":
                    data = str(item.get("content", ""))
                    # Expect a JSON block or tagged content
                    try:
                        payload = json.loads(data)
                        prompt = payload.get("prompt")
                        answer = payload.get("final_platinum_answer") or payload.get("answer")
                    except Exception:
                        # Not JSON; skip
                        continue
                    if self.lorax and prompt and answer:
                        meta = {"source": "autonomy", "ts": int(time.time())}
                        try:
                            self.lorax.online_sft(prompt, answer, metadata=meta)
                        except Exception:
                            pass
        except Exception:
            pass

    async def _update_cognitive_map(self) -> None:
        """Parse training_metadata.jsonl and write summarized skills to cognitive map store.
        If Neo4j credentials exist, write nodes; else snapshot a JSON file for StrategySelector.
        """
        meta_path = self.datasets_dir / "training_metadata.jsonl"
        if not meta_path.exists():
            return
        # Aggregate simple skill confidences
        skills: Dict[str, Dict[str, float]] = {}
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    domain = (j.get("domain") or "general").lower()
                    label = (j.get("label") or "").lower()
                    skills.setdefault(domain, {"count": 0.0, "errors": 0.0})
                    skills[domain]["count"] += 1.0
                    if "factual" in label or "hallucination" in label:
                        skills[domain]["errors"] += 1.0
        except Exception:
            skills = {}

        # Compute confidence per domain
        snapshot: Dict[str, float] = {}
        for dom, vals in skills.items():
            cnt = max(1.0, vals["count"])
            err = max(0.0, vals["errors"])
            conf = max(0.1, 1.0 - (err / cnt))
            snapshot[dom] = round(conf, 3)

        # Try Neo4j if configured
        uri = getattr(self.settings, "neo4j_uri", None) or os.environ.get("NEO4J_URI")
        user = getattr(self.settings, "neo4j_user", None) or os.environ.get("NEO4J_USER")
        pwd = getattr(self.settings, "neo4j_password", None) or os.environ.get("NEO4J_PASSWORD")
        if uri and user and pwd:
            try:
                from neo4j import GraphDatabase  # type: ignore
                driver = GraphDatabase.driver(uri, auth=(user, pwd))
                with driver.session() as session:
                    for name, conf in snapshot.items():
                        session.run(
                            "MERGE (s:Skill {name: $name}) SET s.confidence=$conf, s.status=$status, s.last_updated=timestamp()",
                            name=name, conf=float(conf), status="Developing" if conf < 0.8 else "Mature",
                        )
            except Exception:
                pass
        else:
            # Persist to JSON for StrategySelector to consume
            out = self.base_dir / "cognitive_map.json"
            try:
                out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            except Exception:
                pass