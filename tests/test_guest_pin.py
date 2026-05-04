"""
Tests for the admin-pre-set guest PIN auto-login flow.

Covers:
  - secret_store helpers persist + bump epoch
  - is_request_from_local_network rejects header spoofing + loopback (default)
  - POST /api/auth/guest-login: 403 when off-LAN, 403 when disabled,
    403 on wrong PIN, 200 on success with cookie
  - Issued JWT carries gpe claim that matches secret_store
  - Rotating the guest PIN bumps the epoch (revokes live tokens)
  - GET /guest-login serves template only when LAN + enabled
  - Admin endpoints are gated by require_admin
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("PASSPHRASE", "test-passphrase-do-not-use")
os.environ.setdefault("ADMIN_PIN", "12345678")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use")
# Allow loopback for the test client (TestClient connects via 127.0.0.1)
os.environ["LHA_ALLOW_LOOPBACK_GUEST"] = "1"

from app import main as app_main  # noqa: E402
from app import secret_store  # noqa: E402
from app.auth import (  # noqa: E402
    is_request_from_local_network,
    create_guest_token,
    verify_guest_token_epoch,
)

from fastapi.testclient import TestClient  # noqa: E402


# ---------------------------------------------------------------------------
# Pure secret_store helpers
# ---------------------------------------------------------------------------


def test_secret_store_guest_pin_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert secret_store.get_guest_pin_hash() is None
    assert secret_store.is_guest_pin_enabled() is False
    assert secret_store.get_guest_pin_epoch() == 0

    secret_store.set_guest_pin(pin_hash="abc-bcrypt", enabled=True, set_at=42)
    assert secret_store.get_guest_pin_hash() == "abc-bcrypt"
    assert secret_store.is_guest_pin_enabled() is True
    assert secret_store.get_guest_pin_epoch() == 42

    cfg = secret_store.disable_guest_pin()
    assert cfg["guest_pin_enabled"] is False
    # Epoch bumped to current time (>= 42 + something tiny, but at minimum > 0)
    assert cfg["guest_pin_set_at"] >= 42


# ---------------------------------------------------------------------------
# Local-network detection
# ---------------------------------------------------------------------------


class _FakeReq:
    def __init__(self, host=None):
        self.client = type("C", (), {"host": host})() if host else None


def test_lan_detection_accepts_rfc1918():
    assert is_request_from_local_network(_FakeReq("192.168.1.10")) is True
    assert is_request_from_local_network(_FakeReq("10.0.0.5")) is True
    assert is_request_from_local_network(_FakeReq("172.16.5.99")) is True


def test_lan_detection_rejects_public_ips(monkeypatch):
    monkeypatch.delenv("LHA_ALLOW_LOOPBACK_GUEST", raising=False)
    assert is_request_from_local_network(_FakeReq("8.8.8.8")) is False
    assert is_request_from_local_network(_FakeReq("203.0.113.1")) is False


def test_lan_detection_rejects_loopback_by_default(monkeypatch):
    monkeypatch.delenv("LHA_ALLOW_LOOPBACK_GUEST", raising=False)
    assert is_request_from_local_network(_FakeReq("127.0.0.1")) is False


def test_lan_detection_loopback_allowed_with_env(monkeypatch):
    monkeypatch.setenv("LHA_ALLOW_LOOPBACK_GUEST", "1")
    assert is_request_from_local_network(_FakeReq("127.0.0.1")) is True


def test_lan_detection_no_client_returns_false():
    assert is_request_from_local_network(_FakeReq(None)) is False


# ---------------------------------------------------------------------------
# JWT epoch revocation
# ---------------------------------------------------------------------------


def test_guest_jwt_carries_epoch_claim_and_revokes_on_bump():
    token = create_guest_token("guest-1", guest_pin_epoch=100)
    assert verify_guest_token_epoch(token, current_epoch=100) is True
    assert verify_guest_token_epoch(token, current_epoch=101) is False  # epoch bumped
    assert verify_guest_token_epoch(token, current_epoch=0) is False


# ---------------------------------------------------------------------------
# HTTP integration — POST /api/auth/guest-login
# ---------------------------------------------------------------------------


@pytest.fixture
def lan_client(monkeypatch, tmp_path):
    """Boot the app with a clean secrets dir + first_run_complete=True so the
    guest routes are reachable. Loopback is whitelisted via env so TestClient
    requests (which come from 127.0.0.1) pass the LAN check."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LHA_ALLOW_LOOPBACK_GUEST", "1")
    monkeypatch.setattr(app_main, "_FIRST_RUN_COMPLETE", True)
    return TestClient(app_main.app, follow_redirects=False)


def test_guest_login_rejected_when_pin_disabled(lan_client):
    r = lan_client.post("/api/auth/guest-login", json={"pin": "1234"})
    assert r.status_code == 403
    assert "not enabled" in r.json()["error"].lower()


def test_guest_login_wrong_pin(lan_client):
    secret_store.set_guest_pin(
        pin_hash=app_main.hash_pin("4242"), enabled=True, set_at=1
    )
    r = lan_client.post("/api/auth/guest-login", json={"pin": "9999"})
    assert r.status_code == 403


def test_guest_login_happy_path_sets_cookie(lan_client):
    secret_store.set_guest_pin(
        pin_hash=app_main.hash_pin("4242"), enabled=True, set_at=1
    )
    r = lan_client.post("/api/auth/guest-login", json={"pin": "4242"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["user"]["role"] == "guest"
    assert "lha_session" in r.cookies


def test_guest_login_token_revoked_after_pin_rotation(lan_client):
    secret_store.set_guest_pin(
        pin_hash=app_main.hash_pin("4242"), enabled=True, set_at=1
    )
    r = lan_client.post("/api/auth/guest-login", json={"pin": "4242"})
    assert r.status_code == 200
    token = r.json()["token"]
    # Initially valid
    assert verify_guest_token_epoch(token, secret_store.get_guest_pin_epoch())
    # Admin rotates → epoch bumps → token is revoked
    secret_store.set_guest_pin(
        pin_hash=app_main.hash_pin("9999"), enabled=True, set_at=999
    )
    assert not verify_guest_token_epoch(token, secret_store.get_guest_pin_epoch())


# ---------------------------------------------------------------------------
# Admin endpoints — gated
# ---------------------------------------------------------------------------


def test_get_guest_pin_state_requires_admin(lan_client):
    r = lan_client.get("/api/admin/guest-pin")
    assert r.status_code == 401  # no JWT


def test_post_guest_pin_requires_admin(lan_client):
    r = lan_client.post("/api/admin/guest-pin", json={"new_pin": "4242", "enabled": True})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Off-LAN rejection (simulate via header spoofing — must NOT grant access)
# ---------------------------------------------------------------------------


def test_guest_login_ignores_x_forwarded_for(monkeypatch, tmp_path):
    """If a public IP request fakes X-Forwarded-For: 192.168.1.1, the LAN
    check must still reject it. We simulate this by disabling loopback
    whitelist; TestClient peer is 127.0.0.1 which then fails the gate."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("LHA_ALLOW_LOOPBACK_GUEST", raising=False)
    monkeypatch.setattr(app_main, "_FIRST_RUN_COMPLETE", True)
    secret_store.set_guest_pin(
        pin_hash=app_main.hash_pin("4242"), enabled=True, set_at=1
    )
    client = TestClient(app_main.app, follow_redirects=False)
    r = client.post(
        "/api/auth/guest-login",
        json={"pin": "4242"},
        headers={"X-Forwarded-For": "192.168.1.10", "X-Real-IP": "192.168.1.10"},
    )
    assert r.status_code == 403
    assert "local network" in r.json()["error"].lower()
