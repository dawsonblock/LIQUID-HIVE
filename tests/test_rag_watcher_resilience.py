import os
import io
import json
import pathlib
import asyncio
import tempfile
import time
import shutil
import pytest

from rag_watcher_service import _sha256_file, _load_index_state, _append_index_state, _quarantine, _embed_with_retries, filter_new_files


@pytest.mark.asyncio
async def test_quarantine_on_failure(tmp_path):
    # Prepare a fake ingest dir and file
    ingest_dir = tmp_path / "ingest"
    ingest_dir.mkdir()
    bad_pdf = ingest_dir / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4\nthis is not a valid pdf content\n%%EOF")

    # Set env
    os.environ["INGEST_WATCH_DIR"] = str(ingest_dir)
    # Prepare a dummy retriever that always raises
    class DummyRetriever:
        async def add_documents(self, files):
            raise RuntimeError("embed failed")
    # Run embed with retries which should quarantine
    await _embed_with_retries(DummyRetriever(), [str(bad_pdf)])
    q_failed_dir = pathlib.Path("data/quarantine/failed")
    # File should be moved to quarantine
    assert (q_failed_dir / "bad.pdf").exists()
    # Reason file should exist
    assert (q_failed_dir / "bad.reason.json").exists() or (q_failed_dir / "bad.pdf.reason.json").exists()


def test_dedup_filter(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    sha = _sha256_file(f)
    known = {sha: {"sha256": sha, "path": str(f)}}
    out = filter_new_files(known, [str(f)])
    assert out == []


def test_metrics_exposed_after_ops():
    # After calling quarantine/ok counters, metrics should include our names
    from prometheus_client import generate_latest
    # Touch counters
    from rag_watcher_service import rag_ingest_files_total, rag_chunks_total, rag_quarantine_total
    rag_ingest_files_total.labels(status="ok").inc()
    rag_chunks_total.inc(3)
    rag_quarantine_total.labels(reason="unsupported").inc()
    blob = generate_latest().decode()
    assert "rag_ingest_files_total" in blob
    assert "rag_chunks_total" in blob
    assert "rag_quarantine_total" in blob


def test_index_state_roundtrip(tmp_path):
    state_file = pathlib.Path("data/index_state.jsonl")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    rec = {"sha256": "abc", "path": "/tmp/x"}
    _append_index_state(rec)
    loaded = _load_index_state()
    assert "abc" in loaded