"""Context bridging between user prompts and the RAG/knowledge graph.

This module defines a simple ``ContextBridge`` class that enriches a user
prompt by retrieving relevant documents from the HiveMind RAG index and
formatting them as context.  The resulting enriched prompt is suitable
for consumption by the reasoning agents.

If the retriever is unavailable or returns no results, the original prompt
is returned unchanged.
"""

from __future__ import annotations

from typing import Tuple, Any

try:
    from hivemind.rag.retriever import Retriever
    from hivemind.rag.citations import format_context
except Exception:
    Retriever = None  # type: ignore
    format_context = None  # type: ignore


class ContextBridge:
    """Enriches prompts using the RAG retriever.

    Parameters
    ----------
    retriever: Optional[Retriever]
        The vector search client.  May be ``None`` if the index is not
        available; in that case enrichment does nothing.
    """

    def __init__(self, retriever: Retriever | None) -> None:
        self.retriever = retriever

    async def enrich(self, prompt: str, k: int = 5) -> Tuple[str, str]:
        """Enrich a prompt by retrieving context.

        Parameters
        ----------
        prompt: str
            The user's original question.
        k: int, optional
            Number of documents to fetch from the index.

        Returns
        -------
        Tuple[str, str]
            A tuple ``(enriched_prompt, context)``.  ``context`` will be
            empty if no documents were found or the retriever is not
            configured.
        """
        if not self.retriever or not format_context:
            return prompt, ""
        try:
            docs = self.retriever.search(prompt, k)  # type: ignore[operator]
        except Exception:
            return prompt, ""
        if not docs:
            return prompt, ""
        try:
            context_txt = format_context(docs)  # type: ignore[operator]
        except Exception:
            context_txt = ""
        if not context_txt:
            return prompt, ""
        enriched = (
            f"[CONTEXT]\n{context_txt}\n\n"
            f"[QUESTION]\n{prompt}\n\n"
            "Cite using [#]. If not in context, say 'Not in context'."
        )
        return enriched, context_txt
