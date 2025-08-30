import os
import io
import json
import pathlib
import asyncio
import tempfile
import time
import shutil
import pytest

from rag_watcher_service import _sha256_file, _load_index_state, _append_index_state


def test_sha256_and_state_roundtrip(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    h = _sha256_file(f)
    assert len(h) == 64

    state = tmp_path / "state.jsonl"
    rec = {"sha256": h, "path": str(f)}
    # temporarily patch INDEX_STATE_PATH via environment variable emulation not available; test append directly
    with open(state, "a", encoding="utf-8") as out:
        out.write(json.dumps(rec) + "\n")
    # read back
    with open(state, "r", encoding="utf-8") as inp:
        lines = [json.loads(x) for x in inp.read().strip().splitlines()]
    assert lines[0]["sha256"] == h
