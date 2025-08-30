# LIQUID-HIVE-main/hivemind/rag/retriever.py

from __future__ import annotations
import os
import logging
import json
import time
import pathlib
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
    import faiss # FAISS for vector indexing
    from sentence_transformers import SentenceTransformer # For embedding
    from pypdf import PdfReader # For PDF parsing (if installed)
    DEPS_AVAILABLE = True
except ImportError as e:
    faiss = None
    np = None
    SentenceTransformer = None
    PdfReader = None
    DEPS_AVAILABLE = False
    logging.getLogger(__name__).warning(f"FAISS, NumPy, Sentence Transformers, or PyPDF not installed: {e}. RAG indexing will be disabled.")


# Assuming you have a settings object available
from hivemind.config import Settings # Assuming Settings can be imported here
from capsule_brain.security.input_sanitizer import sanitize_input # To clean document content

log = logging.getLogger(__name__)

# Mock document structure for internal use
class Document:
    def __init__(self, page_content: str, metadata: Dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata

    def to_dict(self):
        return {"page_content": self.page_content, "metadata": self.metadata}

    @staticmethod
    def from_dict(data: Dict[str, Any]):
        return Document(data["page_content"], data["metadata"])


class Retriever:
    """Manages the RAG vector store and document retrieval."""

    def __init__(self, index_dir: str, embed_model_id: str | None) -> None:
        self.index_dir = pathlib.Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.embed_model_id = embed_model_id
        self.embedding_model: Optional[SentenceTransformer] = None
        self.faiss_index: Optional[faiss.IndexFlatL2] = None # Using L2 for simplicity
        self.doc_store: List[Document] = []
        self.is_ready = False

        if self.embed_model_id and DEPS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(self.embed_model_id)
                self.load_or_create_index()
                self.is_ready = True
                log.info(f"RAG Retriever initialized with model: {self.embed_model_id} and index_dir: {self.index_dir}")
            except Exception as e:
                log.error(f"Failed to load embedding model or FAISS index: {e}")
                self.embedding_model = None
                self.is_ready = False
        else:
            log.warning("RAG Retriever initialized without an embedding model (or missing deps). Indexing and search will be disabled.")

    def load_or_create_index(self):
        index_path = self.index_dir / "faiss_index.bin"
        doc_store_path = self.index_dir / "doc_store.json"

        if index_path.exists() and doc_store_path.exists():
            try:
                self.faiss_index = faiss.read_index(str(index_path))
                with open(doc_store_path, "r", encoding="utf-8") as f:
                    raw_docs = json.load(f)
                    self.doc_store = [Document.from_dict(d) for d in raw_docs]
                log.info(f"Loaded existing FAISS index with {len(self.doc_store)} documents.")
            except Exception as e:
                log.error(f"Failed to load existing index: {e}. Creating new index.")
                self.create_new_index()
        else:
            log.info("No existing index found. Creating new index.")
            self.create_new_index()

    def create_new_index(self):
        if self.embedding_model:
            embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
            self.faiss_index = faiss.IndexFlatL2(embedding_dim)
            self.doc_store = []
            self.save_index() # Save empty index initially
            log.info(f"Created new empty FAISS index with dimension {embedding_dim}.")
        else:
            log.error("Cannot create index without an embedding model.")

    def save_index(self):
        if self.faiss_index is not None:
            index_path = self.index_dir / "faiss_index.bin"
            doc_store_path = self.index_dir / "doc_store.json"
            
            faiss.write_index(self.faiss_index, str(index_path))
            with open(doc_store_path, "w", encoding="utf-8") as f:
                json.dump([doc.to_dict() for doc in self.doc_store], f, indent=2)
            log.debug(f"Saved FAISS index with {len(self.doc_store)} documents.")

    async def add_documents(self, file_paths: List[str]) -> List[str]:
        if not self.is_ready or not self.embedding_model or not self.faiss_index:
            log.warning("Retriever not ready to add documents. Embedding model or index not initialized.")
            return []

        indexed_files = []
        new_docs = []
        new_embeddings = []

        for f_path in file_paths:
            try:
                path = pathlib.Path(f_path)
                if not path.exists():
                    log.warning(f"File not found, skipping: {f_path}")
                    continue

                content = ""
                if path.suffix.lower() == ".pdf" and PdfReader is not None:
                    try:
                        reader = PdfReader(f_path)
                        for page in reader.pages:
                            content += page.extract_text() + "\n"
                    except Exception as e:
                        log.warning(f"Failed to parse PDF {f_path}: {e}. Skipping.")
                        continue
                elif path.suffix.lower() in (".txt", ".md"):
                    content = path.read_text(encoding="utf-8")
                else:
                    log.warning(f"Unsupported file type for RAG, skipping: {f_path}")
                    continue

                # Sanitize content before embedding and storing
                cleaned_content = sanitize_input(content)
                if not cleaned_content:
                    log.warning(f"Skipping empty or unsanitizable content from {f_path}")
                    continue

                # Simple chunking if document is too long (optional but recommended for large docs)
                # For now, index as one document. For production, add chunking logic here.
                
                doc = Document(
                    page_content=cleaned_content,
                    metadata={"source": f_path, "timestamp": time.time()}
                )
                new_docs.append(doc)
                new_embeddings.append(self.embedding_model.encode(cleaned_content))
                indexed_files.append(f_path)
                log.info(f"Prepared to index document from {f_path}")

            except Exception as e:
                log.error(f"Error processing file {f_path}: {e}", exc_info=True)

        if new_docs:
            self.faiss_index.add(np.array(new_embeddings).astype('float32'))
            self.doc_store.extend(new_docs)
            self.save_index()
            log.info(f"Successfully indexed {len(new_docs)} new documents.")
        else:
            log.info("No new documents to add after processing.")

        return indexed_files

    async def search(self, query: str, k: int = 5) -> List[Document]:
        if not self.is_ready or not self.embedding_model or not self.faiss_index or not self.doc_store:
            log.warning("Retriever not ready for search. Returning empty results.")
            return []
        if not query.strip():
            return []

        try:
            query_embedding = self.embedding_model.encode(query)
            query_embedding = np.array([query_embedding]).astype('float32')

            D, I = self.faiss_index.search(query_embedding, k) # D is distances, I is indices
            
            results: List[Document] = []
            for idx in I[0]:
                if idx < len(self.doc_store): # Ensure index is valid
                    results.append(self.doc_store[idx])
            log.debug(f"Search for '{query[:50]}' returned {len(results)} results.")
            return results
        except Exception as e:
            log.error(f"Error during RAG search: {e}", exc_info=True)
            return []

    # Placeholder for format_context (can be kept separate or moved here)
    # LIQUID-HIVE-main/hivemind/rag/citations.py (or add this to retriever)
    def format_context(self, documents: List[Document]) -> str:
        if not documents:
            return ""
        
        context_lines = []
        for i, doc in enumerate(documents):
            source = doc.metadata.get("source", "unknown")
            # Simple chunking for display
            snippet = doc.page_content[:200].strip() + ("..." if len(doc.page_content) > 200 else "")
            context_lines.append(f"[{i+1}] Source: {source}\n{snippet}")
        
        return "\n\n".join(context_lines)