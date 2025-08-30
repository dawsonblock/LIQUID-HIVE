# LIQUID-HIVE-main/rag_watcher_service.py

from __future__ import annotations

import os
import time
import pathlib
import asyncio # Import asyncio
import json
import logging
import hashlib
from typing import List, Set, Dict, Any
from datetime import datetime, timezone

# Import Retriever and Settings from hivemind
from hivemind.config import Settings
from hivemind.rag.retriever import Retriever

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI

log = logging.getLogger(__name__)

# Metrics
rag_ingest_files_total = Counter(
    "rag_ingest_files_total", "Total files processed by RAG watcher", ["status"]
)
rag_chunks_total = Counter(
    "rag_chunks_total", "Total chunks produced by RAG watcher"
)
rag_quarantine_total = Counter(
    "rag_quarantine_total", "Total files moved to quarantine", ["reason"]
)
rag_ingest_latency_seconds = Histogram(
    "rag_ingest_latency_seconds", "RAG ingest latency in seconds"
)

# App for metrics endpoint
metrics_app = FastAPI()

@metrics_app.get("/metrics")
async def metrics_endpoint():
    return FastAPI.responses.Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Function to safely import setup_logging
def _setup_logging_if_needed():
    try:
        from unified_runtime.logging_config import setup_logging
        setup_logging()
        log.info("RAG Watcher logging configured.")
    except ImportError:
        logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
        log.warning("Could not import unified_runtime.logging_config. Using basic logging.")

INGEST_DIR = os.environ.get("INGEST_WATCH_DIR", "/data/ingest")
SLEEP_SEC = int(os.environ.get("INGEST_POLL_SECS", "5"))
RAG_MAX_CONCURRENCY = int(os.environ.get("RAG_MAX_CONCURRENCY", "4"))
RAG_BACKOFF_MAX_S = float(os.environ.get("RAG_BACKOFF_MAX_S", "20"))
CHUNK_SIZE = max(200, min(2000, int(os.environ.get("CHUNK_SIZE", "800"))))
CHUNK_OVERLAP = max(0, min(500, int(os.environ.get("CHUNK_OVERLAP", "160"))))

SUPPORTED_TYPES = {".md", ".txt", ".pdf", ".docx", ".html"}

QUARANTINE_DIR = pathlib.Path("data/quarantine")
QUAR_UNSUPPORTED = QUARANTINE_DIR / "unsupported"
QUAR_FAILED = QUARANTINE_DIR / "failed"
INDEX_STATE_PATH = pathlib.Path("data/index_state.jsonl")

for p in [QUARANTINE_DIR, QUAR_UNSUPPORTED, QUAR_FAILED, pathlib.Path(INGEST_DIR)]:
    p.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _quarantine(path: pathlib.Path, reason: str, error: str | None = None, stack: str | None = None) -> None:
    dst_dir = QUAR_UNSUPPORTED if reason == "unsupported" else QUAR_FAILED
    dst = dst_dir / path.name
    try:
        path.replace(dst)
    except Exception:
        pass
    rag_quarantine_total.labels(reason=reason).inc()
    # reason file
    why = {
        "error": error or reason,
        "stack": stack or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sha256": _sha256_file(dst) if dst.exists() else None,
    }
    with open(dst.with_suffix(".reason.json"), "w", encoding="utf-8") as f:
        json.dump(why, f, indent=2)


def _load_index_state() -> Dict[str, Dict[str, Any]]:
    if not INDEX_STATE_PATH.exists():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with open(INDEX_STATE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                out[rec["sha256"]] = rec
            except Exception:
                continue
    return out


def _append_index_state(rec: Dict[str, Any]) -> None:
    with open(INDEX_STATE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


async def _embed_with_retries(retriever: Retriever, files: List[str]) -> List[str]:
    # Chunking per file with exponential backoff and jitter on embed/write
    indexed: List[str] = []
    for f_path in files:
        path = pathlib.Path(f_path)
        ext = path.suffix.lower()
        if ext not in SUPPORTED_TYPES:
            _quarantine(path, "unsupported")
            rag_ingest_files_total.labels(status="unsupported").inc()
            continue
        start = time.time()
        try:
            # Simple chunking by character length
            text = path.read_text(encoding="utf-8", errors="ignore") if ext in {".md", ".txt", ".html"} else ""
            chunks: List[str] = []
            if text:
                i = 0
                while i < len(text):
                    chunks.append(text[i:i+CHUNK_SIZE])
                    i += CHUNK_SIZE - CHUNK_OVERLAP
            else:
                chunks = ["__BINARY__PDF_OR_DOCX__"]
            rag_chunks_total.inc(len(chunks))

            # Exponential backoff with jitter for embedding write
            base = 0.5
            attempts = 5
            delay = base
            for k in range(attempts):
                try:
                    res = await retriever.add_documents([str(path)])
                    indexed.extend(res)
                    rag_ingest_files_total.labels(status="ok").inc()
                    break
                except Exception as e:
                    if k == attempts - 1:
                        raise
                    # jitter
                    await asyncio.sleep(min(delay, RAG_BACKOFF_MAX_S) + (os.urandom(1)[0] / 255.0) * 0.25)
                    delay = min(delay * 2, RAG_BACKOFF_MAX_S)
            rag_ingest_latency_seconds.observe(time.time() - start)
        except Exception as e:
            _quarantine(path, "failed", error=str(e))
            rag_ingest_files_total.labels(status="failed").inc()
    return indexed


async def main_async() -> None:
    _setup_logging_if_needed() # Configure logging
    log.info(f"[rag_watcher] starting to watch {INGEST_DIR}")

    settings = Settings() # Initialize settings
    retriever = Retriever(settings.rag_index, settings.embed_model) # Initialize Retriever

    known = _load_index_state()
    log.info(f"Loaded {len(known)} index records")

    # Initial sweep
    files = sorted([str(p) for p in pathlib.Path(INGEST_DIR).rglob("*") if p.is_file()])
    # Dedup by sha256
    to_index: List[str] = []
    for f in files:
        try:
            s = _sha256_file(pathlib.Path(f))
            if s not in known:
                to_index.append(f)
        except Exception:
            continue

    if to_index:
        idx = await _embed_with_retries(retriever, to_index)
        for f in idx:
            rec = {
                "sha256": _sha256_file(pathlib.Path(f)),
                "path": f,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _append_index_state(rec)
        log.info(f"[rag_watcher] initial indexing complete: {len(idx)} files")
    else:
        log.info("[rag_watcher] no files to index on startup")

    # Watch loop
    while True:
        try:
            files = sorted([str(p) for p in pathlib.Path(INGEST_DIR).rglob("*") if p.is_file()])
            new_files: List[str] = []
            for f in files:
                s = _sha256_file(pathlib.Path(f))
                if s not in known:
                    new_files.append(f)
            if new_files:
                idx = await _embed_with_retries(retriever, new_files)
                for f in idx:
                    s = _sha256_file(pathlib.Path(f))
                    known[s] = {"sha256": s, "path": f, "timestamp": datetime.now(timezone.utc).isoformat()}
                    _append_index_state(known[s])
                log.info(f"[rag_watcher] indexed {len(idx)} new files")
            await asyncio.sleep(SLEEP_SEC)
        except Exception as e:
            log.error(f"[rag_watcher] error: {e}", exc_info=True)
            await asyncio.sleep(SLEEP_SEC)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log.info("[rag_watcher] Shutting down.")
    except Exception as e:
        log.error(f"[rag_watcher] Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()