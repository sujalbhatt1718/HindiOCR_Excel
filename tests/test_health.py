"""Health endpoint tests."""
from __future__ import annotations


def test_health_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert isinstance(body["ocr_loaded"], bool)
    assert isinstance(body["gpu_available"], bool)


def test_openapi_available(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert "/api/upload" in res.json()["paths"]
