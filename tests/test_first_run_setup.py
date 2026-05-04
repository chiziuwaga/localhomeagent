"""
Tests for the first-run setup gate + credential rotation.

These verify:
  - while first_run_complete is false the gate redirects HTML routes to /setup
    and locks /api/* endpoints (other than /api/setup/*, /api/health,
    /api/system/check, /static/*, /favicon)
  - POST /api/setup/credentials with a wrong bootstrap PIN is rejected
  - the happy-path call sets credentials, persists to ~/.local-home-agent
    and flips the gate so the dashboard becomes reachable
  - POST /api/admin/set-pin and /api/admin/rotate-passphrase persist the new
    values to disk

The fixture mutates ``app.main``'s module globals via ``monkeypatch`` rather
than reimporting the module — that keeps function references already imported
by other test modules (``test_system_check``, ``test_platform_pairing``) valid.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Test-only secrets so app.main can import (it requires PASSPHRASE +
# ADMIN_PIN at module-import time). Set BEFORE importing.
os.environ.setdefault("PASSPHRASE", "bootstrap-passphrase-do-not-use")
os.environ.setdefault("ADMIN_PIN", "12345678")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use")

from app import main as app_main  # noqa: E402
from app import secret_store  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

BOOTSTRAP_PIN = "12345678"


@pytest.fixture
def fresh_app(monkeypatch, tmp_path):
    """
    Hand each test a clean ``~/.local-home-agent`` (in tmp_path), a known
    bootstrap PIN hash, and ``_FIRST_RUN_COMPLETE = False``. Monkeypatch
    undoes everything between tests.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Reset app.main globals to "fresh first-run" state
    monkeypatch.setattr(app_main, "_FIRST_RUN_COMPLETE", False)
    monkeypatch.setattr(
        app_main, "ADMIN_PIN_HASH", app_main.hash_pin(BOOTSTRAP_PIN)
    )
    monkeypatch.setattr(
        app_main, "passphrase_swarm",
        app_main.create_passphrase_swarm("bootstrap-passphrase"),
    )

    return {
        "client": TestClient(app_main.app, follow_redirects=False),
        "main": app_main,
        "secret_store": secret_store,
        "bootstrap_pin": BOOTSTRAP_PIN,
        "home": fake_home,
    }


def test_root_redirects_to_setup_until_first_run_complete(fresh_app):
    r = fresh_app["client"].get("/")
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/setup"


def test_dashboard_locked_during_first_run(fresh_app):
    r = fresh_app["client"].get("/dashboard")
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/setup"


def test_health_open_during_first_run(fresh_app):
    r = fresh_app["client"].get("/api/health")
    assert r.status_code == 200


def test_protected_api_locked_during_first_run(fresh_app):
    r = fresh_app["client"].get("/api/admin/permissions")
    assert r.status_code == 423


def test_wrong_bootstrap_pin_rejected(fresh_app):
    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": "00000000",
            "new_pin": "1234",
            "new_passphrase": "this-is-twelve-chars-long",
        },
    )
    assert r.status_code == 403
    assert r.json()["success"] is False


def test_pin_validation_rejects_bad_input(fresh_app):
    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "12",
            "new_passphrase": "this-is-twelve-chars",
        },
    )
    assert r.status_code == 400

    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "abcd",
            "new_passphrase": "this-is-twelve-chars",
        },
    )
    assert r.status_code == 400


def test_passphrase_validation_min_length(fresh_app):
    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "4321",
            "new_passphrase": "too-short",
        },
    )
    assert r.status_code == 400


def test_setup_happy_path_persists_and_locks_endpoint(fresh_app):
    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "987654",
            "new_passphrase": "rotated-passphrase-yes",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    cfg = fresh_app["secret_store"].read_secrets()
    assert cfg["admin_pin"] == "987654"
    assert cfg["passphrase"] == "rotated-passphrase-yes"
    assert cfg["first_run_complete"] is True

    # Endpoint locked once first-run completes
    r2 = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": "987654",
            "new_pin": "1234",
            "new_passphrase": "another-passphrase-12",
        },
    )
    assert r2.status_code == 403


def test_set_pin_persists_to_disk(fresh_app):
    fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "111111",
            "new_passphrase": "first-run-passphrase",
        },
    )
    main = fresh_app["main"]

    class _FakeUser:
        user_id = "admin"
        role = "admin"

    class _FakeRequest:
        class client:
            host = "127.0.0.1"

    req = main.SetPinRequest(current_pin="111111", new_pin="222222")
    import asyncio
    result = asyncio.run(
        main.set_admin_pin(req, _FakeRequest(), _FakeUser())
    )
    assert result == {"success": True, "message": "PIN updated successfully"}
    cfg = fresh_app["secret_store"].read_secrets()
    assert cfg["admin_pin"] == "222222"


def test_rotate_passphrase_persists_to_disk(fresh_app):
    fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "111111",
            "new_passphrase": "initial-passphrase-12",
        },
    )
    main = fresh_app["main"]

    class _FakeUser:
        user_id = "admin"
        role = "admin"

    class _FakeRequest:
        class client:
            host = "127.0.0.1"

    req = main.RotatePassphraseRequest(
        current_pin="111111", new_passphrase="rotated-passphrase-13"
    )
    import asyncio
    result = asyncio.run(
        main.rotate_passphrase(req, _FakeRequest(), _FakeUser())
    )
    assert result == {"success": True, "message": "Passphrase updated successfully"}
    cfg = fresh_app["secret_store"].read_secrets()
    assert cfg["passphrase"] == "rotated-passphrase-13"
