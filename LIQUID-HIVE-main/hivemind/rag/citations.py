"""
Citations and Context Formatting
==============================

This module handles formatting retrieved documents into context for LLM prompts.
It provides citation-style formatting with source attribution.
"""

from __future__ import annotations
from typing import List, Dict, Any
from .retriever import Document


def format_context(documents: List[Document]) -> str:
    """Format retrieved documents into a context string with citations.
    
    Parameters
    ----------
    documents : List[Document]
        List of retrieved documents to format
        
    Returns
    -------
    str
        Formatted context string with citations
    """
    if not documents:
        return ""
    
    context_lines = []
    for i, doc in enumerate(documents):
        source = doc.metadata.get("source", "unknown")
        # Simple chunking for display
        snippet = doc.page_content[:300].strip() + ("..." if len(doc.page_content) > 300 else "")
        context_lines.append(f"[{i+1}] Source: {source}\n{snippet}")
    
    return "\n\n".join(context_lines)


def format_context_with_scores(documents: List[Document], scores: List[float]) -> str:
    """Format retrieved documents with relevance scores.
    
    Parameters
    ----------
    documents : List[Document]
        List of retrieved documents
    scores : List[float]
        Relevance scores for each document
        
    Returns
    -------
    str
        Formatted context string with scores and citations
    """
    if not documents:
        return ""
    
    context_lines = []
    for i, (doc, score) in enumerate(zip(documents, scores)):
        source = doc.metadata.get("source", "unknown")
        snippet = doc.page_content[:300].strip() + ("..." if len(doc.page_content) > 300 else "")
        context_lines.append(f"[{i+1}] Source: {source} (Score: {score:.3f})\n{snippet}")
    
    return "\n\n".join(context_lines)