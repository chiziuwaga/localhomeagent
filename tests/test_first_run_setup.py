"""
Tests for the first-run setup gate + credential rotation.

These verify:
  - while first_run_complete is false the gate redirects HTML routes to /setup
    and locks /api/* endpoints (other than /api/setup/*, /api/health,
    /api/system/check)
  - POST /api/setup/credentials with a wrong bootstrap PIN is rejected
  - the happy-path call sets credentials, persists to ~/.local-home-agent
    and flips the gate so the dashboard becomes reachable
  - POST /api/admin/set-pin and /api/admin/rotate-passphrase persist the new
    values to disk
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def fresh_app(monkeypatch, tmp_path):
    """
    Boot the app with a fresh ``~/.local-home-agent`` rooted in a tempdir, no
    prior secrets, and a known bootstrap PIN. ``monkeypatch`` re-points
    ``Path.home()`` so the secret_store writes inside the tempdir.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    # Force secret_store to read/write inside tmp_path
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Test-only env so app.main can import (it requires PASSPHRASE + ADMIN_PIN
    # at module import time).
    monkeypatch.setenv("PASSPHRASE", "bootstrap-passphrase-do-not-use")
    monkeypatch.setenv("ADMIN_PIN", "12345678")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-do-not-use")

    # Drop any cached import of app.main + secret_store so the module-level
    # state (FIRST_RUN_COMPLETE, ADMIN_PIN_HASH, passphrase_swarm) re-reads
    # the freshly-monkeypatched home.
    for mod in list(sys.modules):
        if mod.startswith("app"):
            del sys.modules[mod]

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    main = importlib.import_module("app.main")
    secret_store = importlib.import_module("app.secret_store")

    from fastapi.testclient import TestClient

    yield {
        "main": main,
        "secret_store": secret_store,
        "client": TestClient(main.app, follow_redirects=False),
        "bootstrap_pin": "12345678",
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
    # /api/admin/permissions normally requires admin auth — the gate should
    # 423-Lock it before auth even runs.
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
    # Too short
    r = fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "12",
            "new_passphrase": "this-is-twelve-chars",
        },
    )
    assert r.status_code == 400
    # Non-digit
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


def test_setup_happy_path_persists_and_unlocks_gate(fresh_app):
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

    # Persisted to disk
    cfg = fresh_app["secret_store"].read_secrets()
    assert cfg["admin_pin"] == "987654"
    assert cfg["passphrase"] == "rotated-passphrase-yes"
    assert cfg["first_run_complete"] is True

    # Setup endpoint is now locked
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
    # Complete first-run first
    fresh_app["client"].post(
        "/api/setup/credentials",
        json={
            "bootstrap_pin": fresh_app["bootstrap_pin"],
            "new_pin": "111111",
            "new_passphrase": "first-run-passphrase",
        },
    )
    # The set_admin_pin route is gated by Depends(require_admin) — invoke the
    # underlying logic directly with a fake admin caller so we don't need to
    # build a real cookie session inside the test.
    main = fresh_app["main"]

    class _FakeUser:
        user_id = "admin"
        role = "admin"

    req = main.SetPinRequest(current_pin="111111", new_pin="222222")

    class _FakeRequest:
        class client:
            host = "127.0.0.1"

    import asyncio

    result = asyncio.run(
        main.set_admin_pin(req, _FakeRequest(), _FakeUser())
    )
    assert result == {"success": True, "message": "PIN updated successfully"}

    # Persisted
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
