from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Dict, List, Optional

from .providers.base import GenReq, GenResp
from .providers.vllm_provider import VLLMProvider
from .providers.openai_provider import OpenAIProvider
from .providers.hf_cpu_provider import HFCpuProvider

try:
    from hivemind.config import Settings
except Exception:
    Settings = None  # type: ignore

log = logging.getLogger(__name__)


class ModelRouter:
    def __init__(self) -> None:
        self.MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "auto").lower()
        self.HF_MODEL = os.environ.get("HF_MODEL")
        self.PROVIDER_TIMEOUT_MS = int(os.environ.get("PROVIDER_TIMEOUT_MS", "120000"))
        self.settings = Settings() if Settings is not None else None

        vllm_endpoint = getattr(self.settings, "vllm_endpoint", None) if self.settings else os.environ.get("VLLM_ENDPOINT")
        vllm_key = getattr(self.settings, "vllm_api_key", None) if self.settings else os.environ.get("VLLM_API_KEY")

        self.vllm = VLLMProvider(vllm_endpoint, vllm_key, timeout_ms=self.PROVIDER_TIMEOUT_MS)
        self.openai = OpenAIProvider(timeout_ms=self.PROVIDER_TIMEOUT_MS)
        self.hf = HFCpuProvider(self.HF_MODEL, timeout_ms=self.PROVIDER_TIMEOUT_MS)

        self._last_provider: Optional[str] = None

    async def providers_status(self) -> Dict[str, bool]:
        v = await self.vllm.health()
        o = await self.openai.health()
        h = await self.hf.health()
        return {"vllm": v, "openai": o, "hf_cpu": h}

    async def any_live(self) -> bool:
        status = await self.providers_status()
        return any(status.values())

    def active_name(self) -> Optional[str]:
        return self._last_provider

    def _order(self) -> List[str]:
        mp = self.MODEL_PROVIDER
        if mp == "vllm":
            return ["vllm"]
        if mp == "openai":
            return ["openai"]
        if mp == "hf_cpu":
            return ["hf_cpu"]
        # auto
        return ["vllm", "openai", "hf_cpu"]

    def _get(self, name: str):
        return {"vllm": self.vllm, "openai": self.openai, "hf_cpu": self.hf}[name]

    async def generate(self, req: GenReq) -> GenResp:
        errors: Dict[str, str] = {}
        for name in self._order():
            prov = self._get(name)
            healthy = False
            try:
                healthy = await prov.health()
            except Exception as e:
                log.warning("Provider %s health check failed on attempt 0: %s", name, e)
                healthy = False
            if not healthy:
                log.warning("Provider %s health check failed on attempt 0", name)
                errors[name] = "unhealthy"
                continue
            # simple per-provider retry with jitter
            for attempt in range(3):
                try:
                    resp = await prov.generate(req)
                    self._last_provider = name
                    return resp
                except Exception as e:
                    log.error(
                        "Provider %s attempt %d failed: %s", name, attempt + 1, e
                    )
                    errors[name] = str(e)
                    await asyncio.sleep(0.1 + random.random() * 0.2)
            # provider exhausted, try next
        # if all failed
        msg = "; ".join([f"{k}: {v}" for k, v in errors.items()]) or "no providers available"
        raise RuntimeError(f"All providers failed: {msg}")
