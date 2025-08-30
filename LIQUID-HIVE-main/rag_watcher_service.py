# LIQUID-HIVE-main/rag_watcher_service.py

from __future__ import annotations

import os
import time
import pathlib
import asyncio # Import asyncio
import json
import logging
from typing import List, Set, Dict, Any

# Import Retriever and Settings from hivemind
from hivemind.config import Settings
from hivemind.rag.retriever import Retriever
# from hivemind.rag.citations import format_context # No longer needed if format_context is part of Retriever


log = logging.getLogger(__name__)

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

def list_files(root: str) -> List[str]:
    p = pathlib.Path(root)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("*.txt", "*.md", "*.pdf"):
        files.extend([str(x) for x in p.rglob(ext)])
    return sorted(files)

# Keep track of indexed files to avoid re-indexing on restart
INDEXED_FILES_STATE_PATH = pathlib.Path(INGEST_DIR) / ".indexed_files.json"

def load_indexed_files_state() -> Set[str]:
    if INDEXED_FILES_STATE_PATH.exists():
        try:
            with open(INDEXED_FILES_STATE_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            log.error(f"Failed to load indexed files state: {e}. Starting fresh.")
    return set()

def save_indexed_files_state(indexed_files: Set[str]):
    try:
        with open(INDEXED_FILES_STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(indexed_files), f, indent=2)
    except Exception as e:
        log.error(f"Failed to save indexed files state: {e}")


async def main_async() -> None:
    _setup_logging_if_needed() # Configure logging
    log.info(f"[rag_watcher] starting to watch {INGEST_DIR}")

    settings = Settings() # Initialize settings
    retriever = Retriever(settings.rag_index, settings.embed_model) # Initialize Retriever

    # Load previously indexed files
    known_indexed_files = load_indexed_files_state()
    log.info(f"Loaded {len(known_indexed_files)} files from previous index state.")
    
    # On startup, re-index any files that might be missing from the index (e.g., if index was deleted)
    # or if they are new since the last run.
    current_files_on_startup = set(list_files(INGEST_DIR))
    files_to_index_on_startup = list(current_files_on_startup - known_indexed_files)
    
    if files_to_index_on_startup:
        log.info(f"[rag_watcher] detected {len(files_to_index_on_startup)} files for initial indexing/re-indexing.")
        indexed_on_startup = await retriever.add_documents(files_to_index_on_startup)
        for f_path in indexed_on_startup:
            known_indexed_files.add(f_path)
        if indexed_on_startup:
            save_indexed_files_state(known_indexed_files)
            log.info(f"[rag_watcher] completed initial indexing of {len(indexed_on_startup)} documents.")
    else:
        log.info("[rag_watcher] no new files for initial indexing.")


    while True:
        try:
            current_files = set(list_files(INGEST_DIR))
            
            # Files that exist but are not yet in our indexed state
            files_to_index = list(current_files - known_indexed_files)
            
            if files_to_index:
                log.info(f"[rag_watcher] detected {len(files_to_index)} new/unindexed files, submitting for processing.")
                indexed_count = 0
                
                successfully_indexed = await retriever.add_documents(files_to_index)
                for f_path in successfully_indexed:
                    known_indexed_files.add(f_path)
                    indexed_count += 1
                
                if indexed_count > 0:
                    log.info(f"[rag_watcher] successfully indexed {indexed_count} new documents.")
                    save_indexed_files_state(known_indexed_files)
                else:
                    log.warning("[rag_watcher] no documents were successfully indexed in this cycle.")
            else:
                log.debug("[rag_watcher] no new files detected.")

        except Exception as e:
            log.error(f"[rag_watcher] error: {e}", exc_info=True)
        
        await asyncio.sleep(SLEEP_SEC)


def main() -> None:
    # This is the synchronous entry point. It needs to run the async part.
    _setup_logging_if_needed() # Configure logging again for the sync wrapper if needed.
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log.info("[rag_watcher] Shutting down.")
    except Exception as e:
        log.error(f"[rag_watcher] Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()