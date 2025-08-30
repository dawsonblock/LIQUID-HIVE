from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional

from .base import GenReq, GenResp

log = logging.getLogger(__name__)


class HFCpuProvider:
    name = "hf_cpu"

    def __init__(self, model_id: Optional[str] = None, timeout_ms: int = 120_000) -> None:
        self.model_id = model_id or os.environ.get("HF_MODEL") or "mistralai/Mistral-7B-Instruct-v0.3"
        self.timeout = timeout_ms / 1000.0
        self._pipeline = None  # lazy

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return
        from transformers import pipeline
        # Allow override to avoid heavy downloads in constrained envs
        model_id = self.model_id
        if os.environ.get("ALLOW_SMALL_HF_MODEL", "0") == "1" and not os.environ.get("HF_MODEL"):
            model_id = "sshleifer/tiny-gpt2"
        self._pipeline = pipeline("text-generation", model=model_id, device_map=None)

    async def health(self) -> bool:
        try:
            # Do not force model download here; just check transformers available
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    async def generate(self, req: GenReq) -> GenResp:
        self._ensure_pipeline()
        # Compose a simple prompt with system + user
        prompt = (req.system + "\n\n" if req.system else "") + req.prompt
        t0 = time.time()
        out = self._pipeline(
            prompt,
            max_new_tokens=int(req.max_tokens),
            do_sample=True,
            temperature=float(req.temperature),
            num_return_sequences=1,
        )
        dt_ms = int((time.time() - t0) * 1000)
        text = out[0]["generated_text"]
        # Return only the continuation beyond the prompt when possible
        if text.startswith(prompt):
            text = text[len(prompt) :].strip()
        meta: Dict[str, Any] = {"latency_ms": dt_ms, "model": self.model_id}
        log.info("generation", extra={"provider": self.name, "latency_ms": dt_ms})
        return GenResp(text=text, provider=self.name, meta=meta)