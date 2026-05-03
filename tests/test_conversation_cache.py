"""
Tests for conversation_cache.py — file-backed persistence.

Covers the core round-trip used by the WebSocket /ws chat handler:
  add_message -> save_session -> (simulate restart by clearing memory cache)
  -> get_session reloads from disk
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.conversation_cache import (
    ConversationCache,
    ConversationMessage,
    ConversationSession,
)


def _run(coro):
    """Helper for sync tests to drive async fns without pytest-asyncio."""
    return asyncio.run(coro)


class TestConversationCachePersistence:
    def test_round_trip_survives_memory_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ConversationCache(cache_dir=Path(tmp))

            async def scenario():
                session = await cache.get_or_create_session("sess-1")
                session.add_message("user", "Hello")
                session.add_message("assistant", "Hi there!")
                await cache.save_session(session)

                # Simulate restart: drop in-memory cache
                cache._memory_cache.clear()

                reloaded = await cache.get_session("sess-1")
                assert reloaded is not None
                assert len(reloaded.messages) == 2
                assert reloaded.messages[0].role == "user"
                assert reloaded.messages[0].content == "Hello"
                assert reloaded.messages[1].role == "assistant"

            _run(scenario())

    def test_get_missing_session_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ConversationCache(cache_dir=Path(tmp))

            async def scenario():
                result = await cache.get_session("does-not-exist")
                assert result is None

            _run(scenario())

    def test_message_serialization_round_trip(self):
        msg = ConversationMessage(role="user", content="hi", metadata={"k": "v"})
        data = msg.to_dict()
        restored = ConversationMessage.from_dict(data)
        assert restored.role == "user"
        assert restored.content == "hi"
        assert restored.metadata == {"k": "v"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
