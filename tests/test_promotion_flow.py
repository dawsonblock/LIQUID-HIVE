import types
from fastapi.testclient import TestClient
from unified_runtime.server import app, adapter_manager


def _auth(client: TestClient):
    return {"X-Admin-Token": "secret"}


def test_start_stop_canary(monkeypatch):
    # inject admin token env
    import os
    os.environ["ADMIN_TOKEN"] = "secret"

    client = TestClient(app)

    # start canary
    r = client.post("/api/admin/start_canary", json={"adapter_id": "adapter_X", "traffic_pct": 15}, headers=_auth(client))
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "started"

    # status check
    r = client.get("/api/admin/status", headers=_auth(client))
    assert r.status_code == 200

    # stop canary
    r = client.post("/api/admin/stop_canary", headers=_auth(client))
    assert r.status_code == 200
    assert r.json().get("status") in ("stopped", "no_manager")


def test_promote(monkeypatch):
    import os
    os.environ["ADMIN_TOKEN"] = "secret"

    client = TestClient(app)

    r = client.post("/api/admin/start_canary", json={"adapter_id": "adapter_Y", "traffic_pct": 10}, headers=_auth(client))
    assert r.status_code == 200

    r = client.post("/api/admin/promote", json={"adapter_id": "adapter_Y"}, headers=_auth(client))
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "promoted"
