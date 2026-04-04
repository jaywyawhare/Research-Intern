from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "session_store" in body


def test_openapi_includes_session_events(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    assert any("events" in p for p in paths)
