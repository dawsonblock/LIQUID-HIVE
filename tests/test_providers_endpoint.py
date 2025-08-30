from fastapi.testclient import TestClient
from unified_runtime.server import app


def test_providers_endpoint_smoke(monkeypatch):
    client = TestClient(app)
    r = client.get('/api/providers')
    assert r.status_code == 200
    body = r.json()
    assert 'providers' in body or 'error' in body
