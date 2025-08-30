"""
Intent modeler
==============

This module defines an ``IntentModeler`` service that periodically analyses
the history of user prompts stored in the CapsuleEngine and synthesises a
long‑term goal representation.  The intent is stored as a special node in
the knowledge graph and can be used by the proactive and retrieval
modules to prioritise context relevant to the operator's current
objectives.

The implementation here is intentionally minimal; it uses simple
heuristics to derive a single sentence summarising the user's goals from
their recent prompts.  In a production system this would call out to a
powerful LLM with a specialised prompt.
"""
from __future__ import annotations

from typing import List, Optional

class IntentModeler:
    """Analyse user prompt history to derive high‑level operator intent."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.current_intent: Optional[str] = None

    async def refresh_intent(self) -> str:
        """Generate a new intent hypothesis based on recent prompts.

        This method fetches the last N user prompts from the Capsule
        engine's memory and produces a naive summary.  The result is
        stored and returned.
        """
        # Retrieve the last N user memory capsules
        try:
            memories: List[dict] = self.engine.get_recent_memories(role="user", limit=20)
        except Exception:
            memories = []
        prompts = [m.get("content", "") for m in memories if isinstance(m, dict)]
        # Simple heuristic: join prompts and truncate
        summary = ", ".join(prompts)[:200]
        if not summary:
            summary = "No recent intent detected."
        self.current_intent = summary
        # Persist the intent in the knowledge graph if available
        try:
            if hasattr(self.engine, "knowledge_graph"):
                kg = self.engine.knowledge_graph
                # store as node with type 'operator_intent'
                kg.add_node(self.current_intent, type="operator_intent")  # type: ignore[attr-defined]
        except Exception:
            pass
        return summary
