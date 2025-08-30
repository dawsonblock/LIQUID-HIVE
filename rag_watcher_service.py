# LIQUID-HIVE-main/rag_watcher_service.py

from __future__ import annotations

import os
import time
import pathlib
import asyncio
import json
import logging
import hashlib
from typing import List, Set, Dict, Any
from datetime import datetime, timezone

# Import Retriever and Settings from hivemind
from hivemind.config import Settings
from hivemind.rag.retriever import Retriever

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, start_http_server

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
RAG_METRICS_PORT = int(os.environ.get("RAG_METRICS_PORT", "8002"))

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


def _log_json(file: str, sha256: str, status: str, num_chunks: int) -> None:
    try:
        payload = {"file": file, "sha256": sha256, "status": status, "num_chunks": num_chunks}
        log.info(json.dumps(payload))
    except Exception:
        pass


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


def filter_new_files(known: Dict[str, Dict[str, Any]], files: List[str]) -> List[str]:
    out: List[str] = []
    for f in files:
        try:
            s = _sha256_file(pathlib.Path(f))
            if s not in known:
                out.append(f)
        except Exception:
            continue
    return out


async def _embed_with_retries(retriever: Retriever, files: List[str]) -> List[str]:
    indexed: List[str] = []
    for f_path in files:
        path = pathlib.Path(f_path)
        ext = path.suffix.lower()
        sha = _sha256_file(path)
        if ext not in SUPPORTED_TYPES:
            _quarantine(path, "unsupported")
            rag_ingest_files_total.labels(status="unsupported").inc()
            _log_json(str(path), sha, "unsupported", 0)
            continue
        start = time.time()
        # Rough chunk estimate for metrics/logs (actual chunking done in retriever)
        num_chunks = 1
        try:
            if ext in {".md", ".txt", ".html"}:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text:
                    i = 0
                    num_chunks = 0
                    while i < len(text):
                        num_chunks += 1
                        i += max(1, CHUNK_SIZE - CHUNK_OVERLAP)
            rag_chunks_total.inc(num_chunks)

            # Exponential backoff with jitter for embedding write
            base = 0.5
            attempts = 5
            delay = base
            success = False
            for k in range(attempts):
                try:
                    res = await retriever.add_documents([str(path)])
                    if res:
                        indexed.extend(res)
                        rag_ingest_files_total.labels(status="ok").inc()
                        success = True
                        break
                    else:
                        raise RuntimeError("indexer_returned_empty")
                except Exception as e:
                    if k == attempts - 1:
                        raise
                    await asyncio.sleep(min(delay, RAG_BACKOFF_MAX_S) + (os.urandom(1)[0] / 255.0) * 0.25)
                    delay = min(delay * 2, RAG_BACKOFF_MAX_S)
            rag_ingest_latency_seconds.observe(time.time() - start)
            _log_json(str(path), sha, "ok" if success else "failed", num_chunks)
        except Exception as e:
            _quarantine(path, "failed", error=str(e))
            rag_ingest_files_total.labels(status="failed").inc()
            _log_json(str(path), sha, "failed", num_chunks)
    return indexed


async def main_async() -> None:
    _setup_logging_if_needed()
    # Start metrics server
    try:
        start_http_server(RAG_METRICS_PORT)
        log.info(f"[rag_watcher] metrics serving on :{RAG_METRICS_PORT}")
    except Exception as e:
        log.warning(f"[rag_watcher] could not start metrics server: {e}")

    log.info(f"[rag_watcher] starting to watch {INGEST_DIR}")

    settings = Settings()
    retriever = Retriever(settings.rag_index, settings.embed_model)

    known = _load_index_state()
    log.info(f"Loaded {len(known)} index records")

    # Initial sweep
    files = sorted([str(p) for p in pathlib.Path(INGEST_DIR).rglob("*") if p.is_file()])
    to_index = filter_new_files(known, files)

    if to_index:
        idx = await _embed_with_retries(retriever, to_index)
        for f in idx:
            rec = {
                "sha256": _sha256_file(pathlib.Path(f)),
                "path": f,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            known[rec["sha256"]] = rec
            _append_index_state(rec)
        log.info(f"[rag_watcher] initial indexing complete: {len(idx)} files")
    else:
        log.info("[rag_watcher] no files to index on startup")

    # Watch loop
    while True:
        try:
            files = sorted([str(p) for p in pathlib.Path(INGEST_DIR).rglob("*") if p.is_file()])
            new_files = filter_new_files(known, files)
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