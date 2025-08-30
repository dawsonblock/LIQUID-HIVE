from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict
import httpx

from .base import GenReq, GenResp

log = logging.getLogger(__name__)


class VLLMProvider:
    name = "vllm"

    def __init__(self, endpoint: str | None, api_key: str | None = None, timeout_ms: int = 120_000) -> None:
        self.endpoint = (endpoint or "").rstrip("/")
        self.api_key = api_key or os.environ.get("VLLM_API_KEY") or os.environ.get("vllm_api_key")
        self.timeout = timeout_ms / 1000.0

    async def health(self) -> bool:
        if not self.endpoint:
            return False
        url = f"{self.endpoint}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception:
            return False

    async def generate(self, req: GenReq) -> GenResp:
        if not self.endpoint:
            raise RuntimeError("vLLM endpoint not configured")
        url = f"{self.endpoint}/v1/chat/completions"
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: Dict[str, Any] = {
            "model": "vllm",
            "messages": [
                {"role": "system", "content": req.system or "You are a helpful assistant."},
                {"role": "user", "content": req.prompt},
            ],
            "max_tokens": int(req.max_tokens),
            "temperature": float(req.temperature),
        }
        if req.stop:
            payload["stop"] = req.stop
        t0 = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        dt_ms = int((time.time() - t0) * 1000)
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        meta = {
            "latency_ms": dt_ms,
            "raw": data,
        }
        log.info("generation", extra={"provider": self.name, "latency_ms": dt_ms})
        return GenResp(text=text, provider=self.name, meta=meta)