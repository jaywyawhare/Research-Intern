from __future__ import annotations

from backend.error_format import format_stored_session_error
from backend.schemas import RegenerateGraphRequest


def test_format_stored_session_error_cloudflare_html():
    html = '<!DOCTYPE html><html><title>524</title></html>'
    msg = format_stored_session_error(RuntimeError(html))
    assert "HTML" in msg or "524" in msg
    assert len(msg) < 500


def test_regenerate_graph_request_defaults_llm_on():
    assert RegenerateGraphRequest().run_llm_analysis is True
    assert RegenerateGraphRequest.model_validate({}).run_llm_analysis is True


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
