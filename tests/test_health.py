"""
Tests for /api/health.

Importing app.main requires PASSPHRASE + ADMIN_PIN environment variables — we
inject test-only values BEFORE importing. The handler must:
  - never raise on subsystem failures
  - report Ollama as unavailable when no provider is reachable (the test box
    has no Ollama running)
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="module")
def client():
    # Test-only secrets so app.main can import without RuntimeError
    os.environ.setdefault("PASSPHRASE", "test-passphrase-do-not-use")
    os.environ.setdefault("ADMIN_PIN", "12345678")

    # Force a fresh import in case another test already imported main with
    # different env. This is safe because each test module re-imports.
    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])

    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_health_returns_200_with_subsystem_keys(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    # Top-level keys
    for key in ("status", "version", "timestamp", "llm", "rbac", "cache", "hardware"):
        assert key in body, f"missing {key}"
    # Status is one of the two known values
    assert body["status"] in ("healthy", "degraded")


def test_health_marks_degraded_when_no_llm(client):
    """No Ollama running on the CI box → status should be 'degraded'."""
    r = client.get("/api/health")
    body = r.json()
    # llm.available should be False on a CI runner without Ollama
    assert body["llm"]["available"] is False
    assert body["status"] == "degraded"
    assert "no local LLM detected" in body.get("degraded_reasons", [])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
