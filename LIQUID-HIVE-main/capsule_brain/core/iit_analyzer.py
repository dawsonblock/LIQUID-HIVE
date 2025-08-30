import asyncio, logging, random, time
from typing import Dict, Any
import networkx as nx

log = logging.getLogger(__name__)

class IITAnalyzer:
    """Lightweight network-based Φ surrogate using clustering × density × size."""
    def __init__(self, engine):
        self.engine = engine
        self.current_phi: float = 0.0
        self.current_glyphs = []
        self.graph = nx.Graph()
        self.last_analysis = time.time()
        self.max_nodes_eval = 200
        self.analysis_interval = 5  # seconds
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        # Seed a small graph; engine may replace with its own knowledge graph
        for i in range(8):
            self.graph.add_node(f"n{i}")
        for i in range(7):
            self.graph.add_edge(f"n{i}", f"n{i+1}")
        self.engine.knowledge_graph = self.graph

    def get_initial_graph(self):
        return self.graph

    def get_latest_metrics(self) -> Dict[str, Any]:
        return {"phi": float(self.current_phi), "glyphs": list(self.current_glyphs), "last": self.last_analysis}

    def _compute_phi(self) -> None:
        n = self.graph.number_of_nodes()
        if n < 2:
            self.current_phi, self.current_glyphs = 0.0, []
            return
        sample_nodes = list(self.graph.nodes())[: min(n, self.max_nodes_eval)]
        subg = self.graph.subgraph(sample_nodes)
        try:
            clustering = nx.average_clustering(subg)
        except Exception:
            clustering = 0.0
        density = nx.density(subg)
        phi = max(0.0, min(clustering * density * n, 10.0))
        self.current_phi = float(phi)
        glyphs = ["○", "◎", "◉"]
        self.current_glyphs = [glyphs[min(int(phi // 1.5), 2)]]
        if n > 20:
            self.current_glyphs.append("⬡")
        if density > 0.3:
            self.current_glyphs.append("▣")
        self.last_analysis = time.time()

    async def run_analysis_loop(self, bus):
        while not self.engine._shutdown_event.is_set():
            try:
                # Add small random wiring evolution
                if random.random() < 0.2 and self.graph.number_of_nodes() < 300:
                    a = f"n{random.randint(0, 9999)}"
                    b = f"n{random.randint(0, 9999)}"
                    self.graph.add_node(a); self.graph.add_node(b)
                    self.graph.add_edge(a, b)
                self._compute_phi()
            except Exception as e:
                log.error("IIT compute error: %s", e)
                self.current_phi, self.current_glyphs = 0.0, []
            await asyncio.sleep(self.analysis_interval)
