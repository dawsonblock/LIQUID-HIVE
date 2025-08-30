from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class KnowledgeFrontier:
    kind: str  # orphan_nodes | weak_component | semantic_gap
    description: str
    nodes: List[str] = field(default_factory=list)
    missing_edge: Optional[Tuple[str, str]] = None


class CuriosityEngine:
    """
    CuriosityEngine periodically analyzes the knowledge graph to identify "frontiers",
    formulates a self-generated research question, submits it for operator approval,
    and upon approval executes an autonomous research & synthesis workflow.

    The engine is resilient: if optional dependencies (Neo4j, roles, retriever) are
    unavailable, it degrades gracefully and still records intents in memory.
    """

    def __init__(
        self,
        engine: Any,
        roles: Optional[Any] = None,
        retriever: Optional[Any] = None,
        settings: Optional[Any] = None,
        loop_interval_sec: int = 900,  # 15 minutes
    ) -> None:
        self.engine = engine
        self.roles = roles
        self.retriever = retriever
        self.settings = settings
        self.loop_interval_sec = loop_interval_sec

        self._task: Optional[asyncio.Task] = None
        self._approvals_task: Optional[asyncio.Task] = None
        self._running = False

        # Storage
        self.base_dir = pathlib.Path(getattr(settings, "runs_dir", "/app/data"))
        self.curiosity_dir = self.base_dir / "curiosity"
        self.curiosity_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="curiosity_frontier_loop")
        self._approvals_task = asyncio.create_task(self._approvals_watcher(), name="curiosity_approvals_watcher")

    async def stop(self) -> None:
        self._running = False
        for t in (self._task, self._approvals_task):
            if t and not t.done():
                t.cancel()
        self._task = None
        self._approvals_task = None

    # ---- Phase 1: Knowledge Frontier ----
    async def _run_loop(self) -> None:
        while self._running:
            try:
                frontiers = await self._analyze_knowledge_graph()
                for fr in frontiers:
                    q = await self._generate_question(fr)
                    if q:
                        await self._submit_curiosity_quest(fr, q)
            except Exception:
                # Never crash the loop
                pass
            await asyncio.sleep(self.loop_interval_sec)

    async def _analyze_knowledge_graph(self) -> List[KnowledgeFrontier]:
        """Analyze the knowledge graph via CapsuleEngine or Neo4j (if available).
        Returns a list of frontier descriptors.
        """
        results: List[KnowledgeFrontier] = []

        # Preferred: use engine hooks if present
        try:
            # Heuristic: engine may expose a graph snapshot
            graph_info = None
            if hasattr(self.engine, "get_graph_snapshot"):
                graph_info = await self.engine.get_graph_snapshot()  # type: ignore
            elif hasattr(self.engine, "knowledge_graph"):
                graph_info = getattr(self.engine, "knowledge_graph")

            if graph_info:
                # Expect nodes: [{id, degree, labels}], edges: [(src, dst)]
                nodes = graph_info.get("nodes", [])
                edges = graph_info.get("edges", [])
                id_to_deg = {n.get("id"): int(n.get("degree", 0)) for n in nodes if n.get("id") is not None}
                # Orphans / near-orphans
                orphan_nodes = [nid for nid, deg in id_to_deg.items() if deg <= 1]
                if orphan_nodes:
                    results.append(KnowledgeFrontier(
                        kind="orphan_nodes",
                        description=f"{len(orphan_nodes)} low-degree nodes detected",
                        nodes=orphan_nodes[:20],
                    ))
                # Weak components: naive detection using edges
                try:
                    comp = self._weakly_connected_components(nodes, edges)
                    if len(comp) > 1:
                        # Identify small components
                        small = [c for c in comp if len(c) < max(5, int(0.05 * len(nodes)))]
                        if small:
                            # Flatten small comps as nodes list
                            nodes_small = [n for sub in small for n in sub][:50]
                            results.append(KnowledgeFrontier(
                                kind="weak_component",
                                description=f"{len(small)} small weakly-connected components",
                                nodes=nodes_small,
                            ))
                except Exception:
                    pass
            # Semantic gaps: heuristic - pick two high-degree nodes with no edge
            try:
                if graph_info:
                    nodes = graph_info.get("nodes", [])
                    edges_set = set()
                    for s, t in graph_info.get("edges", []):
                        edges_set.add((s, t))
                        edges_set.add((t, s))
                    ranked = sorted(nodes, key=lambda n: int(n.get("degree", 0)), reverse=True)
                    if len(ranked) >= 10:
                        a = ranked[0].get("id")
                        b = ranked[1].get("id")
                        if a and b and (a, b) not in edges_set:
                            results.append(KnowledgeFrontier(
                                kind="semantic_gap",
                                description=f"High-degree nodes '{a}' and '{b}' are unconnected",
                                nodes=[a, b],
                                missing_edge=(a, b),
                            ))
            except Exception:
                pass
        except Exception:
            pass

        # Fallback: Neo4j direct analysis if configured
        if not results:
            try:
                uri = getattr(self.settings, "neo4j_uri", None) or os.environ.get("NEO4J_URI")
                user = getattr(self.settings, "neo4j_user", None) or os.environ.get("NEO4J_USER")
                pwd = getattr(self.settings, "neo4j_password", None) or os.environ.get("NEO4J_PASSWORD")
                if uri and user and pwd:
                    try:
                        from neo4j import GraphDatabase  # type: ignore
                    except Exception:
                        return results
                    driver = GraphDatabase.driver(uri, auth=(user, pwd))
                    with driver.session() as session:
                        # Orphans: nodes with degree <= 1
                        orphan = session.run("""
                            MATCH (n)
                            WITH n, size((n)--()) as deg
                            WHERE deg <= 1
                            RETURN n.id as id
                            LIMIT 50
                        """)
                        orphan_ids = [r["id"] for r in orphan if r.get("id")]
                        if orphan_ids:
                            results.append(KnowledgeFrontier(
                                kind="orphan_nodes",
                                description=f"{len(orphan_ids)} low-degree nodes detected",
                                nodes=orphan_ids,
                            ))
            except Exception:
                pass

        return results

    def _weakly_connected_components(self, nodes: List[Dict[str, Any]], edges: List[Tuple[str, str]]):
        idx = {n.get("id"): i for i, n in enumerate(nodes) if n.get("id") is not None}
        parent = list(range(len(idx)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for s, t in edges:
            if s in idx and t in idx:
                union(idx[s], idx[t])

        comps: Dict[int, List[str]] = {}
        rev = {v: k for k, v in idx.items()}
        for i in range(len(idx)):
            r = find(i)
            comps.setdefault(r, []).append(rev[i])
        return list(comps.values())

    # ---- Phase 2: Question Generator ----
    async def _generate_question(self, frontier: KnowledgeFrontier) -> Optional[str]:
        prompt = (
            "You are a Research Scientist AI. You will be given a description of a gap in your own knowledge graph. "
            "Your mission is to formulate a single, powerful, and open-ended question that, if answered, would help you bridge this gap. "
            "The question should provoke deep, non-obvious connections. Return only the question.\n\n"
            f"[FRONTIER_KIND]: {frontier.kind}\n"
            f"[DESCRIPTION]: {frontier.description}\n"
            f"[NODES]: {', '.join(frontier.nodes[:10])}\n"
        )
        try:
            if self.roles is not None:
                # Prefer an Architect-style role if available
                if hasattr(self.roles, "architect"):
                    return await self.roles.architect(prompt)  # type: ignore
                # Fallback to implementer
                if hasattr(self.roles, "implementer"):
                    return await self.roles.implementer(prompt)  # type: ignore
        except Exception:
            pass
        # Fallback heuristic
        if frontier.kind == "semantic_gap" and len(frontier.nodes) >= 2:
            a, b = frontier.nodes[0], frontier.nodes[1]
            return f"What are the shared underlying principles that could bridge '{a}' and '{b}', and what second-order effects might emerge from their integration?"
        if frontier.nodes:
            return f"What unknown relationships connect the following sparse concepts: {', '.join(frontier.nodes[:5])}?"
        return None

    async def _submit_curiosity_quest(self, frontier: KnowledgeFrontier, question: str) -> None:
        quest_id = uuid.uuid4().hex
        payload = {
            "type": "curiosity_quest",
            "id": quest_id,
            "question": question,
            "frontier": frontier.__dict__,
            "ts": int(time.time()),
        }
        text = f"[Curiosity Quest] {json.dumps(payload)}"
        try:
            self.engine.add_memory("approval", text)
        except Exception:
            pass
        # Persist payload for traceability
        try:
            (self.curiosity_dir / f"quest_{quest_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---- Phase 3: Autonomous Research & Synthesis ----
    async def _approvals_watcher(self) -> None:
        """Watches for approval feedback and triggers research workflow."""
        seen: set[str] = set()
        while self._running:
            try:
                events = []
                try:
                    events = list(self.engine.memory)  # type: ignore
                except Exception:
                    events = []
                for item in events:
                    if item.get("role") == "approval_feedback":
                        content = str(item.get("content", ""))
                        if content.startswith("APPROVED: ") and "[Curiosity Quest]" in content:
                            # Extract JSON payload
                            try:
                                json_start = content.index("[Curiosity Quest]") + len("[Curiosity Quest]")
                                payload_str = content[json_start:].strip()
                                payload = json.loads(payload_str)
                                qid = payload.get("id")
                                if qid and qid not in seen:
                                    seen.add(qid)
                                    asyncio.create_task(self._research_workflow(payload))
                            except Exception:
                                pass
                await asyncio.sleep(5)
            except Exception:
                await asyncio.sleep(5)

    async def _research_workflow(self, payload: Dict[str, Any]) -> None:
        quest_id = payload.get("id", uuid.uuid4().hex)
        question = payload.get("question", "")
        workdir = self.curiosity_dir / f"quest_{quest_id}"
        workdir.mkdir(parents=True, exist_ok=True)

        # 1) Decomposition
        subqueries: List[str] = []
        try:
            if self.roles is not None and hasattr(self.roles, "architect"):
                prompt = (
                    "Decompose the following research question into 5-8 specific search queries. "
                    "Return them as bullet points only, one per line.\n\n" + question
                )
                plan = await self.roles.architect(prompt)  # type: ignore
                subqueries = [ln.strip("- •* ") for ln in plan.strip().splitlines() if ln.strip()]
        except Exception:
            pass
        if not subqueries:
            # Heuristic fallback
            subqueries = [question, f"background {question}", f"key concepts {question}"]

        # 2) Exploration (web search or local retrieval)
        docs: List[str] = []
        # Preferred: use retriever if available to avoid external integrations
        try:
            if self.retriever is not None:
                for q in subqueries[:10]:
                    try:
                        res = self.retriever.search(q, k=3)  # type: ignore
                        for d in res:
                            txt = str(getattr(d, "text", getattr(d, "page_content", "")))
                            if txt:
                                docs.append(txt)
                    except Exception:
                        pass
        except Exception:
            pass
        # Persist quarantined docs
        try:
            (workdir / "quarantine.txt").write_text("\n\n---\n\n".join(docs), encoding="utf-8")
        except Exception:
            pass

        # 3) Ingestion: placeholder quarantine stage (could notify rag watcher if available)
        try:
            marker = {"quest_id": quest_id, "count": len(docs), "ts": int(time.time())}
            (workdir / "quarantine_meta.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")
        except Exception:
            pass

        # 4) Synthesis
        synthesis = ""
        try:
            context = "\n\n".join(docs[:20])
            synthesis_prompt = (
                "You are FusionAgent. Synthesize a comprehensive, cited answer to the RESEARCH QUESTION below. "
                "Ground only in the provided CONTEXT; if insufficient, state limitations. Use clear structure.\n\n"
                f"[RESEARCH QUESTION]: {question}\n\n[CONTEXT]:\n{context}\n"
            )
            if self.roles is not None:
                if hasattr(self.roles, "fusion_agent"):
                    synthesis = await self.roles.fusion_agent(synthesis_prompt)  # type: ignore
                elif hasattr(self.roles, "implementer"):
                    synthesis = await self.roles.implementer(synthesis_prompt)  # type: ignore
        except Exception:
            pass

        # Present finding to operator
        finding_payload = {
            "type": "curiosity_finding",
            "quest_id": quest_id,
            "question": question,
            "summary": synthesis,
            "ts": int(time.time()),
        }
        try:
            self.engine.add_memory("approval", f"[Curiosity Finding] {json.dumps(finding_payload)}")
        except Exception:
            pass

        # Record full finding
        try:
            (workdir / "finding.json").write_text(json.dumps(finding_payload, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Await operator approval to merge
        await self._await_merge_decision(quest_id, workdir)

    async def _await_merge_decision(self, quest_id: str, workdir: pathlib.Path) -> None:
        seen = False
        while True:
            try:
                events = []
                try:
                    events = list(self.engine.memory)  # type: ignore
                except Exception:
                    events = []
                for item in events:
                    if item.get("role") == "approval_feedback":
                        content = str(item.get("content", ""))
                        if f"[Curiosity Finding]" in content and "APPROVED:" in content and quest_id in content:
                            # Merge quarantine into main KB; here, mark as merged
                            try:
                                (workdir / "merged").write_text("approved", encoding="utf-8")
                            except Exception:
                                pass
                            try:
                                self.engine.add_memory("self_extension", f"Merged curiosity finding {quest_id} into KB.")
                            except Exception:
                                pass
                            seen = True
                            break
                if seen:
                    break
                await asyncio.sleep(5)
            except Exception:
                await asyncio.sleep(5)