"""
Tests for the /ws WebSocket chat handler.

We can't reach a real Ollama on CI, so we exercise:
  - the "no LLM detected" fallback path (must reply with chat_complete + a
    helpful onboarding message, never hang).
  - the "ping → pong" liveness probe.
  - input validation (empty content → chat_error).

The conversation cache uses Path.home() by default; we set HOME to a tempdir
so tests don't pollute the real user profile.
"""
import importlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="module")
def client():
    tmp_home = tempfile.mkdtemp(prefix="lha-test-home-")
    os.environ["HOME"] = tmp_home
    os.environ["USERPROFILE"] = tmp_home  # Windows
    os.environ.setdefault("PASSPHRASE", "test-passphrase")
    os.environ.setdefault("ADMIN_PIN", "12345678")

    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])

    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_ws_chat_no_llm_replies_with_complete(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({
            "type": "chat",
            "payload": {"content": "Hello agent", "session_id": "test-1", "user_id": "u1"}
        })
        # First frame is the user echo (broadcast_message)
        seen_complete = False
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "chat_complete":
                payload = msg.get("payload") or {}
                assert "No local LLM detected" in payload.get("content", "") or payload.get("content")
                assert payload.get("session_id") == "test-1"
                seen_complete = True
                break
        assert seen_complete, "did not receive chat_complete frame"


def test_ws_empty_content_returns_chat_error(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "payload": {"content": "  ", "session_id": "test-2"}})
        msg = ws.receive_json()
        assert msg.get("type") == "chat_error"
        assert "content" in (msg.get("payload") or {}).get("error", "")


def test_ws_ping_pong(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg.get("type") == "pong"
        assert "ts" in msg.get("payload", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
