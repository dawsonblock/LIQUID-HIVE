from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict
import httpx

from .base import GenReq, GenResp
from unified_runtime.metrics import provider_requests_total, provider_latency_ms

log = logging.getLogger(__name__)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int = 120_000) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout_ms / 1000.0
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")

    async def health(self) -> bool:
        if not self.api_key:
            return False
        url = f"{self.base_url.rstrip('/')}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                return r.status_code == 200
        except Exception:
            return False

    async def generate(self, req: GenReq) -> GenResp:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
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
            "model": self.model,
        }
        provider_requests_total.labels(provider=self.name).inc()
        provider_latency_ms.labels(provider=self.name).observe(dt_ms)
        log.info("generation", extra={"provider": self.name, "latency_ms": dt_ms})
        return GenResp(text=text, provider=self.name, meta=meta)