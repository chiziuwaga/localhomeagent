"""Tests for the agent ↔ platform pairing handshake."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def client():
    """TestClient over a freshly-imported app.main with test-only secrets."""
    os.environ.setdefault("PASSPHRASE", "test-passphrase-do-not-use")
    os.environ.setdefault("ADMIN_PIN", "12345678")
    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolate_pairing_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test gets its own config dir + a clean in-memory active code."""
    from app import platform_pairing

    monkeypatch.setattr(platform_pairing, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(platform_pairing, "PAIRING_FILE", tmp_path / "pairing.json")
    monkeypatch.setattr(platform_pairing, "AGENT_ID_FILE", tmp_path / "agent_id")
    platform_pairing.reset_active_code_for_tests()


def test_init_returns_code_and_agent_id(client) -> None:
    r = client.post("/api/pair/init")
    assert r.status_code == 200
    data = r.json()
    assert len(data["code"]) == 8
    assert data["expires_at"] > 0
    assert len(data["agent_id"]) == 32


def test_confirm_with_valid_code_persists_pairing(client) -> None:
    init = client.post("/api/pair/init").json()
    r = client.post(
        "/api/pair/confirm",
        json={
            "code": init["code"],
            "user_open_id": "u-123",
            "user_email": "test@example.com",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["agent_id"] == init["agent_id"]


def test_confirm_with_wrong_code_rejects(client) -> None:
    client.post("/api/pair/init")
    r = client.post(
        "/api/pair/confirm",
        json={"code": "WRONGGGG", "user_open_id": "u-123"},
    )
    assert r.status_code == 400


def test_confirm_without_init_rejects(client) -> None:
    r = client.post(
        "/api/pair/confirm",
        json={"code": "ANY00000", "user_open_id": "u-123"},
    )
    assert r.status_code == 400


def test_status_when_unpaired(client) -> None:
    r = client.get("/api/pair/status")
    assert r.status_code == 200
    body = r.json()
    assert body["paired"] is False
    assert len(body["agent_id"]) == 32


def test_status_after_pairing(client) -> None:
    init = client.post("/api/pair/init").json()
    client.post(
        "/api/pair/confirm",
        json={"code": init["code"], "user_open_id": "u-456"},
    )
    r = client.get("/api/pair/status")
    assert r.status_code == 200
    body = r.json()
    assert body["paired"] is True
    assert body["user_open_id"] == "u-456"


def test_unpair_removes_pairing(client) -> None:
    init = client.post("/api/pair/init").json()
    client.post(
        "/api/pair/confirm",
        json={"code": init["code"], "user_open_id": "u-789"},
    )
    r = client.post("/api/pair/unpair")
    assert r.status_code == 200
    assert r.json()["success"] is True
    status = client.get("/api/pair/status").json()
    assert status["paired"] is False
