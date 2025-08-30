"""
Dataset build utilities for text and vision‑language (VL)
=======================================================

This module extends the dataset build to also extract VL supervision from run logs.
It produces two datasets by default under datasets/:

- sft_text.jsonl: supervised text pairs
- sft_vl.jsonl: supervised VL pairs {image_path, text}
"""
from __future__ import annotations

import json, os
from pathlib import Path
from typing import Iterable, Dict, Any

DS_DIR = Path("datasets")
DS_DIR.mkdir(parents=True, exist_ok=True)


def iter_run_logs(runs_dir: str) -> Iterable[Dict[str, Any]]:
    p = Path(runs_dir)
    for f in p.glob("*.jsonl"):
        try:
            for line in f.read_text().splitlines():
                yield json.loads(line)
        except Exception:
            continue


def build_text_sft_and_prefs(runs_dir: str = "runs") -> None:
    """Existing (simplified) text dataset builder that extracts SFT pairs."""
    sft_path = DS_DIR / "sft_text.jsonl"
    with sft_path.open("w", encoding="utf-8") as out:
        for rec in iter_run_logs(runs_dir):
            kind = rec.get("kind")
            pay = rec.get("payload", {})
            if kind == "text_single":
                q = pay.get("question", "")
                a = pay.get("winner", "")
                if q and a:
                    out.write(json.dumps({"prompt": q, "completion": a})+"\n")
            elif kind == "text_committee":
                q = pay.get("question", "")
                a = pay.get("merged", "")
                if q and a:
                    out.write(json.dumps({"prompt": q, "completion": a})+"\n")
            elif kind == "text_debate":
                q = pay.get("question", "")
                a = pay.get("winner", "")
                if q and a:
                    out.write(json.dumps({"prompt": q, "completion": a})+"\n")


def build_vl_sft(runs_dir: str = "runs") -> None:
    """Build sft_vl.jsonl from VL interactions in run logs."""
    vl_path = DS_DIR / "sft_vl.jsonl"
    with vl_path.open("w", encoding="utf-8") as out:
        for rec in iter_run_logs(runs_dir):
            kind = rec.get("kind")
            pay = rec.get("payload", {})
            if kind == "vision_committee":
                q = pay.get("question", "")
                ans = pay.get("synthesized_answer") or pay.get("winner") or ""
                image_path = pay.get("image_path") or pay.get("image_uri") or ""
                if q and ans and image_path:
                    out.write(json.dumps({
                        "image_path": image_path,
                        "text": f"Question: {q}\nAnswer: {ans}",
                        "meta": {"ts": rec.get("ts"), "model": pay.get("model"), "adapter": pay.get("adapter"), "strategy": pay.get("strategy")}
                    })+"\n")

__all__ = ["build_text_sft_and_prefs", "build_vl_sft"]