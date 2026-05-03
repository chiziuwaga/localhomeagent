"""
Queue Authentication Module - Per-Queue Auth for Multi-Resident Isolation
Ensures residents only receive messages from queues they're authorized to access

Architecture:
============

Multi-Tenant Queue Model:
-------------------------
Each resident has their own isolated message queue. Queues are namespaced by:
1. Room/Unit ID (e.g., "room_101")
2. User ID (e.g., "user_abc123")
3. Channel type (e.g., "private", "room_broadcast", "property_wide")

┌─────────────────────────────────────────────────────────────────────────────┐
│                        Message Routing Architecture                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│  Private Q    │            │   Room Q      │            │  Property Q   │
│  user_abc123  │            │   room_101    │            │   all_rooms   │
└───────────────┘            └───────────────┘            └───────────────┘
        │                              │                              │
        │ Only this user               │ Only room members            │ All residents
        │                              │                              │
        ▼                              ▼                              ▼
   [user_abc123]              [user_abc123,                    [Everyone]
                               user_def456]

Security Model:
---------------
1. Queue subscription requires JWT token with queue scope
2. Admin can broadcast to any queue
3. Residents can only subscribe to their own queues + room queues
4. Guests can only receive from waiting_room queue

Token Claims:
-------------
{
    "sub": "user_abc123",
    "role": "resident",
    "room_id": "room_101",
    "queues": ["user_abc123", "room_101", "all_rooms"],
    "exp": 1234567890
}
"""

import jwt
import hashlib
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class QueueType(Enum):
    """Types of message queues"""
    PRIVATE = "private"       # User-specific queue
    ROOM = "room"             # Room/unit shared queue
    PROPERTY = "property"     # Property-wide announcements
    ADMIN = "admin"           # Admin-only queue
    GUEST = "guest"           # Guest waiting room queue


@dataclass
class QueuePermission:
    """Permission for a specific queue"""
    queue_id: str
    queue_type: QueueType
    can_read: bool = True
    can_write: bool = False
    can_admin: bool = False


@dataclass
class QueueToken:
    """JWT token claims for queue access"""
    user_id: str
    role: str
    room_id: Optional[str]
    queues: List[str]
    issued_at: datetime
    expires_at: datetime
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    def can_access(self, queue_id: str) -> bool:
        """Check if this token grants access to a queue"""
        return queue_id in self.queues or self.role == "admin"


class QueueAuthManager:
    """
    Manages queue authentication and authorization for multi-resident isolation.
    
    Ensures:
    1. Residents can only subscribe to authorized queues
    2. Messages are routed to correct recipients
    3. Admin can override for emergency broadcasts
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or self._load_or_generate_secret()
        self._active_subscriptions: Dict[str, Set[str]] = {}  # queue_id -> set of user_ids
        self._user_queues: Dict[str, Set[str]] = {}  # user_id -> set of queue_ids
        self._queue_metadata: Dict[str, Dict] = {}  # queue_id -> metadata
    
    def _load_or_generate_secret(self) -> str:
        """Load or generate JWT secret key"""
        secret_path = Path("config/queue_secret.key")
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        
        if secret_path.exists():
            return secret_path.read_text().strip()
        
        # Generate new secret
        import secrets
        new_secret = secrets.token_hex(32)
        secret_path.write_text(new_secret)
        logger.info("Generated new queue authentication secret")
        return new_secret
    
    # -------------------------------------------------------------------------
    # Token Management
    # -------------------------------------------------------------------------
    
    def create_token(
        self,
        user_id: str,
        role: str,
        room_id: Optional[str] = None,
        additional_queues: Optional[List[str]] = None,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create a JWT token for queue access.
        
        Args:
            user_id: The user's unique identifier
            role: User role (admin, resident, guest)
            room_id: Optional room assignment
            additional_queues: Extra queues to grant access to
            expires_in_hours: Token validity period
        
        Returns:
            Signed JWT token string
        """
        now = datetime.now()
        expires = now + timedelta(hours=expires_in_hours)
        
        # Build queue list based on role and room
        queues = self._compute_queue_permissions(user_id, role, room_id)
        
        # Add any additional queues
        if additional_queues:
            queues.extend(additional_queues)
        
        # Remove duplicates
        queues = list(set(queues))
        
        claims = {
            "sub": user_id,
            "role": role,
            "room_id": room_id,
            "queues": queues,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp())
        }
        
        token = jwt.encode(claims, self._secret_key, algorithm="HS256")
        logger.info(f"Created queue token for {user_id} with access to {len(queues)} queues")
        
        return token
    
    def verify_token(self, token: str) -> Optional[QueueToken]:
        """
        Verify and decode a queue access token.
        
        Args:
            token: JWT token string
        
        Returns:
            QueueToken if valid, None if invalid/expired
        """
        try:
            claims = jwt.decode(token, self._secret_key, algorithms=["HS256"])
            
            return QueueToken(
                user_id=claims["sub"],
                role=claims["role"],
                room_id=claims.get("room_id"),
                queues=claims.get("queues", []),
                issued_at=datetime.fromtimestamp(claims["iat"]),
                expires_at=datetime.fromtimestamp(claims["exp"])
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Queue token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid queue token: {e}")
            return None
    
    def _compute_queue_permissions(
        self,
        user_id: str,
        role: str,
        room_id: Optional[str]
    ) -> List[str]:
        """Compute which queues a user should have access to"""
        queues = []
        
        # Everyone gets their private queue
        queues.append(f"user_{user_id}")
        
        if role == "admin":
            # Admins get access to all queues
            queues.append("admin")
            queues.append("all_rooms")
            queues.append("waiting_room")
            # Add all room queues
            for queue_id, metadata in self._queue_metadata.items():
                if metadata.get("type") == QueueType.ROOM.value:
                    queues.append(queue_id)
        
        elif role == "resident":
            # Residents get their room queue and property-wide
            if room_id:
                queues.append(f"room_{room_id}")
            queues.append("all_rooms")  # Property announcements
        
        elif role == "guest":
            # Guests only get waiting room
            queues.append("waiting_room")
        
        return queues
    
    # -------------------------------------------------------------------------
    # Queue Management
    # -------------------------------------------------------------------------
    
    def create_queue(
        self,
        queue_id: str,
        queue_type: QueueType,
        owner_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Create a new message queue"""
        if queue_id in self._queue_metadata:
            logger.warning(f"Queue {queue_id} already exists")
            return False
        
        self._queue_metadata[queue_id] = {
            "type": queue_type.value,
            "owner": owner_id,
            "created": datetime.now().isoformat(),
            **(metadata or {})
        }
        self._active_subscriptions[queue_id] = set()
        
        logger.info(f"Created queue: {queue_id} ({queue_type.value})")
        return True
    
    def subscribe(
        self,
        queue_id: str,
        user_id: str,
        token: str
    ) -> bool:
        """
        Subscribe a user to a queue.
        
        Args:
            queue_id: Queue to subscribe to
            user_id: User requesting subscription
            token: Queue access token
        
        Returns:
            True if subscription granted
        """
        # Verify token
        queue_token = self.verify_token(token)
        if not queue_token:
            logger.warning(f"Invalid token for subscription: {user_id} -> {queue_id}")
            return False
        
        # Check token belongs to user
        if queue_token.user_id != user_id:
            logger.warning(f"Token user mismatch: {queue_token.user_id} != {user_id}")
            return False
        
        # Check queue access
        if not queue_token.can_access(queue_id):
            logger.warning(f"User {user_id} not authorized for queue {queue_id}")
            return False
        
        # Grant subscription
        if queue_id not in self._active_subscriptions:
            self._active_subscriptions[queue_id] = set()
        
        self._active_subscriptions[queue_id].add(user_id)
        
        if user_id not in self._user_queues:
            self._user_queues[user_id] = set()
        self._user_queues[user_id].add(queue_id)
        
        logger.info(f"User {user_id} subscribed to queue {queue_id}")
        return True
    
    def unsubscribe(self, queue_id: str, user_id: str) -> bool:
        """Unsubscribe a user from a queue"""
        if queue_id in self._active_subscriptions:
            self._active_subscriptions[queue_id].discard(user_id)
        
        if user_id in self._user_queues:
            self._user_queues[user_id].discard(queue_id)
        
        return True
    
    def unsubscribe_all(self, user_id: str) -> int:
        """Unsubscribe a user from all queues (e.g., on disconnect)"""
        count = 0
        if user_id in self._user_queues:
            for queue_id in list(self._user_queues[user_id]):
                self.unsubscribe(queue_id, user_id)
                count += 1
        return count
    
    def get_subscribers(self, queue_id: str) -> Set[str]:
        """Get all users subscribed to a queue"""
        return self._active_subscriptions.get(queue_id, set())
    
    def get_user_queues(self, user_id: str) -> Set[str]:
        """Get all queues a user is subscribed to"""
        return self._user_queues.get(user_id, set())
    
    # -------------------------------------------------------------------------
    # Message Routing
    # -------------------------------------------------------------------------
    
    def route_message(
        self,
        queue_id: str,
        message: Dict[str, Any],
        sender_id: str,
        sender_token: str
    ) -> List[str]:
        """
        Route a message to queue subscribers.
        
        Args:
            queue_id: Target queue
            message: Message content
            sender_id: Sender's user ID
            sender_token: Sender's queue token
        
        Returns:
            List of user IDs that should receive the message
        """
        # Verify sender has write permission
        token = self.verify_token(sender_token)
        if not token:
            logger.warning(f"Invalid sender token for routing")
            return []
        
        # Check if sender can write to this queue
        # Admins can write anywhere, others need to be subscribed
        if token.role != "admin" and not token.can_access(queue_id):
            logger.warning(f"User {sender_id} cannot write to queue {queue_id}")
            return []
        
        # Get subscribers
        subscribers = self.get_subscribers(queue_id)
        
        # Don't send to self
        subscribers = subscribers - {sender_id}
        
        logger.info(f"Routing message to {len(subscribers)} subscribers in {queue_id}")
        return list(subscribers)
    
    def broadcast_to_all(self, message: Dict[str, Any], admin_token: str) -> List[str]:
        """
        Admin broadcast to all connected users.
        
        Args:
            message: Message content
            admin_token: Admin's queue token
        
        Returns:
            List of all user IDs that should receive the message
        """
        token = self.verify_token(admin_token)
        if not token or token.role != "admin":
            logger.warning("Broadcast attempted without admin token")
            return []
        
        # Collect all subscribed users
        all_users = set()
        for subscribers in self._active_subscriptions.values():
            all_users.update(subscribers)
        
        logger.info(f"Admin broadcast to {len(all_users)} users")
        return list(all_users)


# -------------------------------------------------------------------------
# Singleton instance
# -------------------------------------------------------------------------

_queue_auth_manager: Optional[QueueAuthManager] = None


def get_queue_auth_manager() -> QueueAuthManager:
    """Get the singleton queue auth manager instance"""
    global _queue_auth_manager
    if _queue_auth_manager is None:
        _queue_auth_manager = QueueAuthManager()
        
        # Create default queues
        _queue_auth_manager.create_queue("waiting_room", QueueType.GUEST)
        _queue_auth_manager.create_queue("all_rooms", QueueType.PROPERTY)
        _queue_auth_manager.create_queue("admin", QueueType.ADMIN)
        
    return _queue_auth_manager


# -------------------------------------------------------------------------
# FastAPI Integration
# -------------------------------------------------------------------------

def create_queue_auth_routes(app):
    """Register queue authentication API routes"""
    from fastapi import APIRouter, HTTPException, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from .auth import get_current_user, AuthenticatedUser

    router = APIRouter(prefix="/api/queues", tags=["queue-auth"])
    security = HTTPBearer()
    manager = get_queue_auth_manager()

    @router.post("/token")
    async def get_queue_token(
        room_id: Optional[str] = None,
        caller: AuthenticatedUser = Depends(get_current_user),
    ):
        """Get a queue access token for the authenticated user"""
        token = manager.create_token(caller.user_id, caller.role, room_id)
        return {"token": token}
    
    @router.post("/subscribe/{queue_id}")
    async def subscribe_to_queue(
        queue_id: str,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Subscribe to a message queue"""
        token = manager.verify_token(credentials.credentials)
        if not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        success = manager.subscribe(queue_id, token.user_id, credentials.credentials)
        if not success:
            raise HTTPException(status_code=403, detail="Not authorized for this queue")
        
        return {"success": True, "queue": queue_id}
    
    @router.delete("/subscribe/{queue_id}")
    async def unsubscribe_from_queue(
        queue_id: str,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Unsubscribe from a message queue"""
        token = manager.verify_token(credentials.credentials)
        if not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        manager.unsubscribe(queue_id, token.user_id)
        return {"success": True}
    
    @router.get("/subscriptions")
    async def get_my_subscriptions(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Get queues the current user is subscribed to"""
        token = manager.verify_token(credentials.credentials)
        if not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        queues = manager.get_user_queues(token.user_id)
        return {"queues": list(queues)}
    
    @router.post("/room/{room_id}")
    async def create_room_queue(
        room_id: str,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Create a queue for a room (admin only)"""
        token = manager.verify_token(credentials.credentials)
        if not token or token.role != "admin":
            raise HTTPException(status_code=403, detail="Admin only")
        
        queue_id = f"room_{room_id}"
        success = manager.create_queue(queue_id, QueueType.ROOM)
        return {"success": success, "queue_id": queue_id}
    
    app.include_router(router)
    return router
