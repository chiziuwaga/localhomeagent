"""
Communication Protocol for Local Home Agent
Handles person-to-person messaging, family chat, and notifications
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import json


class MessageType(str, Enum):
    """Type of message"""
    DIRECT = "direct"  # One-to-one message
    ROOM = "room"  # Group chat message
    BROADCAST = "broadcast"  # Broadcast to all users
    SYSTEM = "system"  # System notification


class MessageStatus(str, Enum):
    """Status of message delivery"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class ChatMessage(BaseModel):
    """Individual chat message"""
    id: str
    type: MessageType
    sender_id: str
    sender_name: str
    recipient_id: Optional[str] = None  # For direct messages
    room_id: Optional[str] = None  # For room messages
    content: str
    timestamp: datetime
    status: MessageStatus = MessageStatus.SENT
    read_by: List[str] = []  # User IDs who have read the message


class ChatRoom(BaseModel):
    """Chat room for group conversations"""
    id: str
    name: str
    description: Optional[str] = None
    members: List[str]  # User IDs
    created_by: str
    created_at: datetime
    is_private: bool = False


class FamilyChat:
    """
    Family/Resident Chat System
    Manages person-to-person and group chat functionality
    """
    
    def __init__(self):
        self.messages: List[ChatMessage] = []
        self.rooms: List[ChatRoom] = []
        self.unread_counts: Dict[str, int] = {}  # user_id -> unread count
    
    def create_room(self, name: str, members: List[str], created_by: str, 
                    description: Optional[str] = None, is_private: bool = False) -> ChatRoom:
        """Create a new chat room"""
        room = ChatRoom(
            id=f"room_{len(self.rooms)}_{datetime.now().timestamp()}",
            name=name,
            description=description,
            members=members,
            created_by=created_by,
            created_at=datetime.now(),
            is_private=is_private
        )
        self.rooms.append(room)
        return room
    
    def send_direct_message(self, sender_id: str, sender_name: str, 
                           recipient_id: str, content: str) -> ChatMessage:
        """Send a direct message to another user"""
        message = ChatMessage(
            id=f"msg_{len(self.messages)}_{datetime.now().timestamp()}",
            type=MessageType.DIRECT,
            sender_id=sender_id,
            sender_name=sender_name,
            recipient_id=recipient_id,
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        
        # Increment unread count for recipient
        if recipient_id not in self.unread_counts:
            self.unread_counts[recipient_id] = 0
        self.unread_counts[recipient_id] += 1
        
        return message
    
    def send_room_message(self, sender_id: str, sender_name: str, 
                         room_id: str, content: str) -> ChatMessage:
        """Send a message to a chat room"""
        room = self.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")
        
        if sender_id not in room.members:
            raise ValueError(f"User {sender_id} is not a member of room {room_id}")
        
        message = ChatMessage(
            id=f"msg_{len(self.messages)}_{datetime.now().timestamp()}",
            type=MessageType.ROOM,
            sender_id=sender_id,
            sender_name=sender_name,
            room_id=room_id,
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        
        # Increment unread count for all members except sender
        for member_id in room.members:
            if member_id != sender_id:
                if member_id not in self.unread_counts:
                    self.unread_counts[member_id] = 0
                self.unread_counts[member_id] += 1
        
        return message
    
    def send_broadcast(self, sender_id: str, sender_name: str, content: str) -> ChatMessage:
        """Send a broadcast message to all users"""
        message = ChatMessage(
            id=f"msg_{len(self.messages)}_{datetime.now().timestamp()}",
            type=MessageType.BROADCAST,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        return message
    
    def mark_as_read(self, message_id: str, user_id: str):
        """Mark a message as read by a user"""
        message = next((m for m in self.messages if m.id == message_id), None)
        if message and user_id not in message.read_by:
            message.read_by.append(user_id)
            message.status = MessageStatus.READ
            
            # Decrement unread count
            if user_id in self.unread_counts and self.unread_counts[user_id] > 0:
                self.unread_counts[user_id] -= 1
    
    def get_messages_for_user(self, user_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get all messages for a user (direct messages, room messages, broadcasts)"""
        user_messages = []
        
        for message in self.messages:
            # Direct messages where user is sender or recipient
            if message.type == MessageType.DIRECT:
                if message.sender_id == user_id or message.recipient_id == user_id:
                    user_messages.append(message)
            
            # Room messages where user is a member
            elif message.type == MessageType.ROOM:
                room = self.get_room(message.room_id)
                if room and user_id in room.members:
                    user_messages.append(message)
            
            # Broadcast messages
            elif message.type == MessageType.BROADCAST:
                user_messages.append(message)
        
        # Sort by timestamp (newest first) and limit
        user_messages.sort(key=lambda m: m.timestamp, reverse=True)
        return user_messages[:limit]
    
    def get_conversation(self, user1_id: str, user2_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get conversation between two users"""
        conversation = [
            m for m in self.messages
            if m.type == MessageType.DIRECT and (
                (m.sender_id == user1_id and m.recipient_id == user2_id) or
                (m.sender_id == user2_id and m.recipient_id == user1_id)
            )
        ]
        conversation.sort(key=lambda m: m.timestamp)
        return conversation[-limit:]
    
    def get_room_messages(self, room_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get messages in a chat room"""
        room_messages = [
            m for m in self.messages
            if m.type == MessageType.ROOM and m.room_id == room_id
        ]
        room_messages.sort(key=lambda m: m.timestamp)
        return room_messages[-limit:]
    
    def get_room(self, room_id: str) -> Optional[ChatRoom]:
        """Get a chat room by ID"""
        return next((r for r in self.rooms if r.id == room_id), None)
    
    def get_user_rooms(self, user_id: str) -> List[ChatRoom]:
        """Get all rooms a user is a member of"""
        return [r for r in self.rooms if user_id in r.members]
    
    def get_unread_count(self, user_id: str) -> int:
        """Get unread message count for a user"""
        return self.unread_counts.get(user_id, 0)


class NotificationSystem:
    """
    Notification System
    Handles system notifications and alerts
    """
    
    def __init__(self):
        self.notifications: List[Dict[str, Any]] = []
    
    def send_notification(self, user_id: str, title: str, message: str, 
                         notification_type: str = "info") -> Dict[str, Any]:
        """Send a notification to a user"""
        notification = {
            "id": f"notif_{len(self.notifications)}_{datetime.now().timestamp()}",
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,  # info, warning, error, success
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        self.notifications.append(notification)
        return notification
    
    def get_user_notifications(self, user_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        user_notifs = [n for n in self.notifications if n["user_id"] == user_id]
        
        if unread_only:
            user_notifs = [n for n in user_notifs if not n["read"]]
        
        user_notifs.sort(key=lambda n: n["timestamp"], reverse=True)
        return user_notifs
    
    def mark_notification_read(self, notification_id: str):
        """Mark a notification as read"""
        notif = next((n for n in self.notifications if n["id"] == notification_id), None)
        if notif:
            notif["read"] = True


class SecureMessenger:
    """
    Secure Message Passing with HMAC-SHA256
    For sensitive communications between residents and admin
    """
    
    def __init__(self, secret_key: str = "default_secret_key"):
        self.secret_key = secret_key.encode()
    
    def sign_message(self, message: str) -> str:
        """Sign a message with HMAC-SHA256"""
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_message(self, message: str, signature: str) -> bool:
        """Verify a message signature"""
        expected_signature = self.sign_message(message)
        return hmac.compare_digest(expected_signature, signature)
    
    def encrypt_message(self, message: str) -> Dict[str, str]:
        """Create a signed message package"""
        signature = self.sign_message(message)
        return {
            "message": message,
            "signature": signature,
            "timestamp": datetime.now().isoformat()
        }
    
    def decrypt_message(self, package: Dict[str, str]) -> Optional[str]:
        """Verify and extract message from package"""
        if self.verify_message(package["message"], package["signature"]):
            return package["message"]
        return None


# Global instances
family_chat = FamilyChat()
notification_system = NotificationSystem()
secure_messenger = SecureMessenger()


# Helper functions
def get_family_chat() -> FamilyChat:
    """Get the global family chat instance"""
    return family_chat


def get_notification_system() -> NotificationSystem:
    """Get the global notification system instance"""
    return notification_system


def get_secure_messenger() -> SecureMessenger:
    """Get the global secure messenger instance"""
    return secure_messenger


# FastAPI Router
from fastapi import APIRouter, HTTPException, Query


def create_communication_routes() -> APIRouter:
    """Create FastAPI router for communication endpoints"""
    router = APIRouter(prefix="/api/communication", tags=["communication"])
    
    # ─────────────────────────────────────────────────────────────────────────
    # Chat Room Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    class CreateRoomRequest(BaseModel):
        name: str
        members: List[str]
        description: Optional[str] = None
        is_private: bool = False
    
    @router.post("/rooms")
    async def create_room(request: CreateRoomRequest, created_by: str = Query(...)):
        """Create a new chat room"""
        room = family_chat.create_room(
            name=request.name,
            members=request.members,
            created_by=created_by,
            description=request.description,
            is_private=request.is_private
        )
        return {"status": "created", "room": room.model_dump()}
    
    @router.get("/rooms")
    async def get_user_rooms(user_id: str = Query(...)):
        """Get all rooms for a user"""
        rooms = family_chat.get_user_rooms(user_id)
        return {"rooms": [r.model_dump() for r in rooms]}
    
    @router.get("/rooms/{room_id}")
    async def get_room(room_id: str):
        """Get a specific room"""
        room = family_chat.get_room(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        return {"room": room.model_dump()}
    
    @router.get("/rooms/{room_id}/messages")
    async def get_room_messages(room_id: str, limit: int = Query(50)):
        """Get messages for a room"""
        messages = family_chat.get_room_messages(room_id, limit)
        return {"messages": [m.model_dump() for m in messages]}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Direct Message Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    class SendMessageRequest(BaseModel):
        sender_id: str
        sender_name: str
        content: str
    
    @router.post("/messages/direct/{recipient_id}")
    async def send_direct_message(recipient_id: str, request: SendMessageRequest):
        """Send a direct message"""
        message = family_chat.send_direct_message(
            sender_id=request.sender_id,
            sender_name=request.sender_name,
            recipient_id=recipient_id,
            content=request.content
        )
        return {"status": "sent", "message": message.model_dump()}
    
    @router.post("/messages/room/{room_id}")
    async def send_room_message(room_id: str, request: SendMessageRequest):
        """Send a message to a room"""
        message = family_chat.send_room_message(
            sender_id=request.sender_id,
            sender_name=request.sender_name,
            room_id=room_id,
            content=request.content
        )
        return {"status": "sent", "message": message.model_dump()}
    
    @router.get("/messages/direct")
    async def get_direct_messages(user_id: str = Query(...), other_user_id: str = Query(...), limit: int = Query(50)):
        """Get direct messages between two users"""
        messages = family_chat.get_direct_messages(user_id, other_user_id, limit)
        return {"messages": [m.model_dump() for m in messages]}
    
    @router.post("/messages/{message_id}/read")
    async def mark_message_read(message_id: str, user_id: str = Query(...)):
        """Mark a message as read"""
        family_chat.mark_as_read(message_id, user_id)
        return {"status": "marked_read"}
    
    @router.get("/unread-count")
    async def get_unread_count(user_id: str = Query(...)):
        """Get unread message count for a user"""
        count = family_chat.get_unread_count(user_id)
        return {"user_id": user_id, "unread_count": count}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Notification Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    class SendNotificationRequest(BaseModel):
        user_id: str
        title: str
        message: str
        notification_type: str = "info"
    
    @router.post("/notifications")
    async def send_notification(request: SendNotificationRequest):
        """Send a notification to a user"""
        notif = notification_system.send_notification(
            user_id=request.user_id,
            title=request.title,
            message=request.message,
            notification_type=request.notification_type
        )
        return {"status": "sent", "notification": notif}
    
    @router.get("/notifications")
    async def get_notifications(user_id: str = Query(...), unread_only: bool = Query(False)):
        """Get notifications for a user"""
        notifs = notification_system.get_user_notifications(user_id, unread_only)
        return {"notifications": notifs}
    
    @router.post("/notifications/{notification_id}/read")
    async def mark_notification_read(notification_id: str):
        """Mark a notification as read"""
        notification_system.mark_notification_read(notification_id)
        return {"status": "marked_read"}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Secure Messenger Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    class SecureMessageRequest(BaseModel):
        message: str
    
    class VerifyMessageRequest(BaseModel):
        message: str
        signature: str
    
    @router.post("/secure/sign")
    async def sign_message(request: SecureMessageRequest):
        """Sign a message for secure transmission"""
        package = secure_messenger.encrypt_message(request.message)
        return {"package": package}
    
    @router.post("/secure/verify")
    async def verify_message(request: VerifyMessageRequest):
        """Verify a signed message"""
        is_valid = secure_messenger.verify_message(request.message, request.signature)
        return {"valid": is_valid}
    
    return router
