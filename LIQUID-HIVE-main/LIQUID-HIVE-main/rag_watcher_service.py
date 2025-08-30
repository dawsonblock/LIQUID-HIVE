"""
Minimal RAG watcher service.

Watches an ingest directory for text-like files and triggers Retriever index rebuilds.
This is a placeholder for local dev; replace with production-grade watcher as needed.
"""
from __future__ import annotations

import os
import time
import pathlib
from typing import List

INGEST_DIR = os.environ.get("INGEST_WATCH_DIR", "/data/ingest")
SLEEP_SEC = int(os.environ.get("INGEST_POLL_SECS", "5"))


def list_files(root: str) -> List[str]:
    p = pathlib.Path(root)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("*.txt", "*.md", "*.pdf"):
        files.extend([str(x) for x in p.rglob(ext)])
    return sorted(files)


def main() -> None:
    print(f"[rag_watcher] watching {INGEST_DIR}")
    known = set(list_files(INGEST_DIR))
    while True:
        try:
            current = set(list_files(INGEST_DIR))
            added = current - known
            if added:
                for f in sorted(added):
                    print(f"[rag_watcher] new file: {f}")
                # In a fuller implementation, call into hivemind.rag to index
                # For now, just update known set.
                known = current
        except Exception as e:
            print(f"[rag_watcher] error: {e}")
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main()