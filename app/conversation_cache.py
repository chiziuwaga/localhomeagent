"""
Conversation Cache for Local Home Agent
Provides file-based JSON persistence for conversation state.

Features:
- Local file storage (no database needed)
- Session-based conversation management
- Automatic cleanup of old sessions
- Memory-first with file backup
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import asyncio

logger = logging.getLogger(__name__)

# Cache directory (user's local data)
CACHE_DIR = Path.home() / ".local-home-agent" / "conversations"


@dataclass
class ConversationMessage:
    """A single message in a conversation"""
    role: str  # 'user', 'assistant', 'system', 'thinking'
    content: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConversationMessage":
        return ConversationMessage(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationSession:
    """A conversation session with messages and metadata"""
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": self.context,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConversationSession":
        return ConversationSession(
            session_id=data.get("session_id", ""),
            messages=[ConversationMessage.from_dict(m) for m in data.get("messages", [])],
            created_at=data.get("created_at", datetime.now().timestamp()),
            updated_at=data.get("updated_at", datetime.now().timestamp()),
            context=data.get("context", {})
        )

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> ConversationMessage:
        """Add a message to the conversation"""
        msg = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now().timestamp(),
            metadata=metadata or {}
        )
        self.messages.append(msg)
        self.updated_at = datetime.now().timestamp()
        return msg

    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Get the most recent N messages"""
        return self.messages[-count:] if len(self.messages) > count else self.messages


class ConversationCache:
    """
    Manages conversation persistence with file-based storage.
    
    Usage:
        cache = ConversationCache()
        session = await cache.get_or_create_session("user-123")
        session.add_message("user", "Hello!")
        await cache.save_session(session)
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 168):
        """
        Initialize the conversation cache.
        
        Args:
            cache_dir: Directory for storing conversation files
            max_age_hours: Maximum age of sessions before cleanup (default 7 days)
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.max_age_hours = max_age_hours
        self._memory_cache: Dict[str, ConversationSession] = {}
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Conversation cache directory: {self.cache_dir}")
        except Exception as e:
            logger.warning(f"Could not create cache directory: {e}")

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session"""
        # Sanitize session_id for safe filename
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self.cache_dir / f"{safe_id}.json"

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get a conversation session by ID.
        First checks memory cache, then file storage.
        """
        # Check memory cache first
        if session_id in self._memory_cache:
            return self._memory_cache[session_id]

        # Try to load from file
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                with open(session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = ConversationSession.from_dict(data)
                self._memory_cache[session_id] = session
                logger.debug(f"Loaded session {session_id} from file")
                return session
            except Exception as e:
                logger.error(f"Failed to load session {session_id}: {e}")
                return None

        return None

    async def get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create a new one"""
        session = await self.get_session(session_id)
        if session is None:
            session = ConversationSession(session_id=session_id)
            self._memory_cache[session_id] = session
            logger.info(f"Created new session: {session_id}")
        return session

    async def save_session(self, session: ConversationSession) -> bool:
        """
        Save a session to both memory and file storage.
        """
        try:
            # Update memory cache
            self._memory_cache[session.session_id] = session
            session.updated_at = datetime.now().timestamp()

            # Save to file
            session_path = self._get_session_path(session.session_id)
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2)

            logger.debug(f"Saved session {session.session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from memory and file storage"""
        try:
            # Remove from memory
            if session_id in self._memory_cache:
                del self._memory_cache[session_id]

            # Delete file
            session_path = self._get_session_path(session_id)
            if session_path.exists():
                session_path.unlink()

            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def cleanup_old_sessions(self) -> int:
        """Remove sessions older than max_age_hours. Returns count deleted."""
        cutoff = datetime.now().timestamp() - (self.max_age_hours * 3600)
        deleted_count = 0

        try:
            for session_file in self.cache_dir.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("updated_at", 0) < cutoff:
                        session_file.unlink()
                        session_id = data.get("session_id", "")
                        if session_id in self._memory_cache:
                            del self._memory_cache[session_id]
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Error processing {session_file}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old sessions")
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")

        return deleted_count

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions (basic metadata only)"""
        sessions = []
        try:
            for session_file in self.cache_dir.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "message_count": len(data.get("messages", [])),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    })
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")

        return sessions


# Global instance
_conversation_cache: Optional[ConversationCache] = None


def get_conversation_cache() -> ConversationCache:
    """Get or create the global conversation cache instance"""
    global _conversation_cache
    if _conversation_cache is None:
        _conversation_cache = ConversationCache()
    return _conversation_cache
