import asyncio
import types
import os
import pytest

from unified_runtime.model_router import ModelRouter
from unified_runtime.providers.base import GenReq


class DummyProv:
    def __init__(self, healthy=True, text="ok", name="dummy"):
        self._healthy = healthy
        self._text = text
        self.name = name
        self.calls = 0
    async def health(self):
        return self._healthy
    async def generate(self, req: GenReq):
        self.calls += 1
        class R:
            def __init__(self, t, n):
                self.text = t
                self.provider = n
                self.meta = {}
        return R(self._text, self.name)


@pytest.mark.asyncio
async def test_auto_fallback_openai(monkeypatch):
    router = ModelRouter()

    v = DummyProv(healthy=False, name="vllm")
    o = DummyProv(healthy=True, text="from openai", name="openai")
    h = DummyProv(healthy=True, text="from hf", name="hf_cpu")

    monkeypatch.setattr(router, "vllm", v)
    monkeypatch.setattr(router, "openai", o)
    monkeypatch.setattr(router, "hf", h)

    resp = await router.generate(GenReq(prompt="hi"))
    assert resp.text == "from openai"
    assert resp.provider == "openai"


@pytest.mark.asyncio
async def test_auto_fallback_hf(monkeypatch):
    router = ModelRouter()

    v = DummyProv(healthy=False, name="vllm")
    o = DummyProv(healthy=False, name="openai")
    h = DummyProv(healthy=True, text="cpu path", name="hf_cpu")

    monkeypatch.setattr(router, "vllm", v)
    monkeypatch.setattr(router, "openai", o)
    monkeypatch.setattr(router, "hf", h)

    resp = await router.generate(GenReq(prompt="hi"))
    assert resp.text == "cpu path"
    assert resp.provider == "hf_cpu"


@pytest.mark.asyncio
async def test_providers_status(monkeypatch):
    router = ModelRouter()

    v = DummyProv(healthy=False, name="vllm")
    o = DummyProv(healthy=True, name="openai")
    h = DummyProv(healthy=True, name="hf_cpu")

    monkeypatch.setattr(router, "vllm", v)
    monkeypatch.setattr(router, "openai", o)
    monkeypatch.setattr(router, "hf", h)

    status = await router.providers_status()
    assert status == {"vllm": False, "openai": True, "hf_cpu": True}
