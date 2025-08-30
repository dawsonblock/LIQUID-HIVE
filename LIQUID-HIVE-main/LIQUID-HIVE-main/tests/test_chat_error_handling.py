import asyncio
import types
import httpx
import pytest

from unified_runtime.server import app
from fastapi.testclient import TestClient

client = TestClient(app)


class DummyRoles:
    async def implementer(self, prompt: str):
        raise httpx.RequestError("network down")


def test_chat_httpx_request_error(monkeypatch):
    # Monkeypatch roles and minimal state
    from unified_runtime import server as srv
    srv.engine = types.SimpleNamespace(add_memory=lambda r, c: None)
    srv.text_roles = DummyRoles()
    srv.judge = types.SimpleNamespace()  # not used here
    srv.settings = types.SimpleNamespace(MODEL_ROUTING_ENABLED=False)

    r = client.post('/api/chat', params={'q': 'hello'})
    assert r.status_code == 200
    body = r.json()
    assert 'Error communicating with the model endpoint' in body['answer']


def test_chat_keyerror_handling(monkeypatch):
    class BadRoles:
        async def implementer(self, prompt: str):
            return { 'unexpected': 'shape' }  # Force downstream KeyError in policy handling

    from unified_runtime import server as srv
    srv.engine = types.SimpleNamespace(add_memory=lambda r, c: None)
    srv.text_roles = BadRoles()
    srv.judge = types.SimpleNamespace(rank=lambda a, prompt: {}, merge=lambda a, b: 'ok')
    srv.settings = types.SimpleNamespace(MODEL_ROUTING_ENABLED=False, committee_k=1)

    # We patch decide_policy to access wrong keys
    def bad_decide_policy(**kwargs):
        raise KeyError('missing key')

    srv.decide_policy = bad_decide_policy

    r = client.post('/api/chat', params={'q': 'hello'})
    assert r.status_code == 200
    body = r.json()
    assert 'Error processing model response or policy' in body['answer']