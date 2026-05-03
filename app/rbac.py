"""
Role-Based Access Control (RBAC) System for Local Home Agent

This module provides a robust hierarchical role system where:
- ADMIN is the parent/root role with full permissions
- RESIDENT inherits base permissions + room-specific device access
- GUEST has limited permissions with expiry time

Features:
- User registration with room/unit assignment
- Device assignment per user/role
- Hierarchical permission inheritance
- Messaging system for network users
- Guest invitation and expiry management

PDF §4.2.3, §4.5.4 compliance
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import hashlib
import secrets
import logging
import json

logger = logging.getLogger(__name__)


# ===========================================
# ROLE HIERARCHY
# ===========================================

class RoleType(str, Enum):
    """Role types in hierarchical order (ADMIN is parent of all)"""
    ADMIN = "admin"           # Full control - parent role
    OPERATOR = "operator"     # Property manager (can manage residents)
    RESIDENT = "resident"     # Standard resident with room access
    GUEST = "guest"           # Temporary limited access
    DEVICE = "device"         # IoT device role (for device-to-device auth)


class PermissionType(str, Enum):
    """All available permissions"""
    # Device control
    DEVICE_CONTROL = "device_control"
    DEVICE_CONTROL_LIMITED = "device_control_limited"
    DEVICE_MANAGE = "device_manage"           # Add/remove devices
    
    # Scene/automation
    SCENE_ACTIVATE = "scene_activate"
    SCENE_CREATE = "scene_create"
    AUTOMATION_CREATE = "automation_create"
    
    # Security
    LOCK_CONTROL = "lock_control"
    ALARM_CONTROL = "alarm_control"
    CAMERA_VIEW = "camera_view"
    CAMERA_MANAGE = "camera_manage"
    
    # Communication
    CHAT = "chat"
    BROADCAST_MESSAGE = "broadcast_message"   # Send to all users
    DIRECT_MESSAGE = "direct_message"         # Send to specific users
    
    # Administration
    USER_MANAGE = "user_manage"               # Add/remove users
    ROLE_ASSIGN = "role_assign"               # Change user roles
    PERMISSION_MANAGE = "permission_manage"   # Modify permissions
    VIEW_AUDIT_LOGS = "view_audit_logs"
    VIEW_ENERGY_LOGS = "view_energy_logs"
    SYSTEM_CONFIG = "system_config"           # System settings
    
    # Guest management
    GUEST_INVITE = "guest_invite"
    GUEST_REVOKE = "guest_revoke"


# Default permissions per role (inherits downward)
ROLE_HIERARCHY: Dict[RoleType, List[RoleType]] = {
    RoleType.ADMIN: [RoleType.OPERATOR, RoleType.RESIDENT, RoleType.GUEST],
    RoleType.OPERATOR: [RoleType.RESIDENT, RoleType.GUEST],
    RoleType.RESIDENT: [RoleType.GUEST],
    RoleType.GUEST: [],
    RoleType.DEVICE: [],
}

DEFAULT_ROLE_PERMISSIONS: Dict[RoleType, Set[PermissionType]] = {
    RoleType.ADMIN: {p for p in PermissionType},  # All permissions
    
    RoleType.OPERATOR: {
        PermissionType.DEVICE_CONTROL,
        PermissionType.DEVICE_MANAGE,
        PermissionType.SCENE_ACTIVATE,
        PermissionType.SCENE_CREATE,
        PermissionType.LOCK_CONTROL,
        PermissionType.CAMERA_VIEW,
        PermissionType.CHAT,
        PermissionType.BROADCAST_MESSAGE,
        PermissionType.DIRECT_MESSAGE,
        PermissionType.USER_MANAGE,
        PermissionType.GUEST_INVITE,
        PermissionType.GUEST_REVOKE,
        PermissionType.VIEW_AUDIT_LOGS,
        PermissionType.VIEW_ENERGY_LOGS,
    },
    
    RoleType.RESIDENT: {
        PermissionType.DEVICE_CONTROL,
        PermissionType.SCENE_ACTIVATE,
        PermissionType.CAMERA_VIEW,
        PermissionType.CHAT,
        PermissionType.DIRECT_MESSAGE,
        PermissionType.GUEST_INVITE,
        PermissionType.VIEW_ENERGY_LOGS,
    },
    
    RoleType.GUEST: {
        PermissionType.DEVICE_CONTROL_LIMITED,
        PermissionType.CHAT,
    },
    
    RoleType.DEVICE: set(),  # Devices have specific permissions per device
}


# ===========================================
# DATA MODELS
# ===========================================

@dataclass
class RoomUnit:
    """A room/unit in the co-living space"""
    id: str
    name: str                           # e.g., "Room 101", "Suite A"
    floor: Optional[int] = None
    building: Optional[str] = None
    assigned_devices: List[str] = field(default_factory=list)  # Device IDs
    max_occupants: int = 1
    current_occupants: List[str] = field(default_factory=list)  # User IDs


@dataclass
class NetworkUser:
    """A user on the local network"""
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: RoleType = RoleType.GUEST
    room_id: Optional[str] = None       # Assigned room/unit
    custom_permissions: Set[str] = field(default_factory=set)   # Additional permissions
    denied_permissions: Set[str] = field(default_factory=set)   # Explicitly denied
    assigned_devices: List[str] = field(default_factory=list)   # Personal device access
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # For guests
    last_seen: Optional[datetime] = None
    is_active: bool = True
    access_token: Optional[str] = None
    pin_hash: Optional[str] = None      # For verification
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role.value,
            "room_id": self.room_id,
            "custom_permissions": list(self.custom_permissions),
            "denied_permissions": list(self.denied_permissions),
            "assigned_devices": self.assigned_devices,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_active": self.is_active,
        }


@dataclass
class DeviceAssignment:
    """Assignment of IoT device to user/room"""
    device_id: str
    device_name: str
    entity_id: Optional[str] = None     # Home Assistant entity_id
    assigned_to_room: Optional[str] = None
    assigned_to_users: List[str] = field(default_factory=list)
    allowed_roles: List[RoleType] = field(default_factory=lambda: [RoleType.ADMIN])
    is_high_risk: bool = False          # Requires extra verification
    control_permissions: Set[str] = field(default_factory=lambda: {"on", "off"})


@dataclass
class NetworkMessage:
    """Message sent to users on the network"""
    id: str
    sender_id: str
    sender_name: str
    recipient_ids: List[str]            # Empty = broadcast to all
    content: str
    message_type: str = "info"          # info, alert, warning, emergency
    created_at: datetime = field(default_factory=datetime.now)
    read_by: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "recipient_ids": self.recipient_ids,
            "content": self.content,
            "message_type": self.message_type,
            "created_at": self.created_at.isoformat(),
            "read_by": self.read_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# ===========================================
# RBAC MANAGER
# ===========================================

class RBACManager:
    """
    Manages users, roles, permissions, and device assignments
    
    Key principle: Admin is the PARENT role - all permissions inherit from Admin.
    """
    
    def __init__(self):
        self.users: Dict[str, NetworkUser] = {}
        self.rooms: Dict[str, RoomUnit] = {}
        self.device_assignments: Dict[str, DeviceAssignment] = {}
        self.messages: List[NetworkMessage] = []
        self.role_permissions = DEFAULT_ROLE_PERMISSIONS.copy()
        
        # Create default admin user
        self._create_default_admin()
        
        # Create sample rooms
        self._create_sample_rooms()
    
    def _create_default_admin(self):
        """Create the default admin user"""
        admin = NetworkUser(
            id="admin-001",
            name="Property Admin",
            email="admin@coliving.local",
            role=RoleType.ADMIN,
            pin_hash=self._hash_pin("1234"),
        )
        self.users[admin.id] = admin
        logger.info("Created default admin user")
    
    def _create_sample_rooms(self):
        """Create sample room structure"""
        rooms = [
            RoomUnit(id="room-101", name="Room 101", floor=1),
            RoomUnit(id="room-102", name="Room 102", floor=1),
            RoomUnit(id="room-201", name="Room 201", floor=2),
            RoomUnit(id="room-202", name="Room 202", floor=2),
            RoomUnit(id="common-1", name="Common Area", floor=1, max_occupants=10),
            RoomUnit(id="kitchen-1", name="Shared Kitchen", floor=1, max_occupants=5),
        ]
        for room in rooms:
            self.rooms[room.id] = room
    
    @staticmethod
    def _hash_pin(pin: str) -> str:
        """Hash a PIN for storage"""
        return hashlib.sha256(pin.encode()).hexdigest()
    
    @staticmethod
    def _generate_token() -> str:
        """Generate a secure access token"""
        return secrets.token_urlsafe(32)
    
    # ===========================================
    # USER MANAGEMENT
    # ===========================================
    
    def create_user(
        self,
        name: str,
        role: RoleType = RoleType.RESIDENT,
        room_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        expiry_hours: Optional[int] = None,
        creator_id: Optional[str] = None,
    ) -> NetworkUser:
        """
        Create a new user on the network
        
        Args:
            name: User's display name
            role: User's role (default: RESIDENT)
            room_id: Assigned room/unit ID
            email: Optional email
            phone: Optional phone number
            expiry_hours: For guests, hours until access expires
            creator_id: ID of user creating this account
        
        Returns:
            The created NetworkUser
        """
        # Verify creator has permission
        if creator_id:
            creator = self.users.get(creator_id)
            if creator and not self.has_permission(creator_id, PermissionType.USER_MANAGE):
                if role != RoleType.GUEST or not self.has_permission(creator_id, PermissionType.GUEST_INVITE):
                    raise PermissionError("Creator lacks permission to create users")
        
        user_id = f"user-{secrets.token_hex(4)}"
        
        expires_at = None
        if role == RoleType.GUEST and expiry_hours:
            expires_at = datetime.now() + timedelta(hours=expiry_hours)
        
        user = NetworkUser(
            id=user_id,
            name=name,
            email=email,
            phone=phone,
            role=role,
            room_id=room_id,
            expires_at=expires_at,
            access_token=self._generate_token(),
        )
        
        self.users[user_id] = user
        
        # Assign to room
        if room_id and room_id in self.rooms:
            self.rooms[room_id].current_occupants.append(user_id)
        
        logger.info(f"Created user: {name} ({role.value}) in {room_id}")
        return user
    
    def get_user(self, user_id: str) -> Optional[NetworkUser]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def get_user_by_token(self, token: str) -> Optional[NetworkUser]:
        """Get user by access token"""
        for user in self.users.values():
            if user.access_token == token and user.is_active:
                # Check expiry
                if user.expires_at and datetime.now() > user.expires_at:
                    user.is_active = False
                    return None
                user.last_seen = datetime.now()
                return user
        return None
    
    def list_users(
        self,
        role: Optional[RoleType] = None,
        room_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[NetworkUser]:
        """List users with optional filters"""
        users = list(self.users.values())
        
        if role:
            users = [u for u in users if u.role == role]
        
        if room_id:
            users = [u for u in users if u.room_id == room_id]
        
        if active_only:
            now = datetime.now()
            users = [
                u for u in users 
                if u.is_active and (not u.expires_at or u.expires_at > now)
            ]
        
        return users
    
    def update_user_role(
        self,
        user_id: str,
        new_role: RoleType,
        updater_id: str,
    ) -> bool:
        """Update a user's role (admin only)"""
        updater = self.users.get(updater_id)
        if not updater or updater.role != RoleType.ADMIN:
            raise PermissionError("Only admin can change user roles")
        
        user = self.users.get(user_id)
        if not user:
            return False
        
        old_role = user.role
        user.role = new_role
        logger.info(f"User {user.name} role changed: {old_role.value} -> {new_role.value}")
        return True
    
    def deactivate_user(self, user_id: str, admin_id: str) -> bool:
        """Deactivate a user (admin/operator only)"""
        if not self.has_permission(admin_id, PermissionType.USER_MANAGE):
            raise PermissionError("Permission denied")
        
        user = self.users.get(user_id)
        if not user:
            return False
        
        user.is_active = False
        user.access_token = None
        logger.info(f"User deactivated: {user.name}")
        return True
    
    # ===========================================
    # PERMISSION CHECKING
    # ===========================================
    
    def has_permission(self, user_id: str, permission: PermissionType) -> bool:
        """
        Check if a user has a specific permission
        
        Permission resolution order:
        1. Check if explicitly denied
        2. Check if explicitly granted (custom_permissions)
        3. Check role-based permissions
        4. Check inherited permissions from parent roles
        """
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False
        
        # Check expiry
        if user.expires_at and datetime.now() > user.expires_at:
            user.is_active = False
            return False
        
        perm_str = permission.value if isinstance(permission, PermissionType) else permission
        
        # 1. Explicit deny overrides everything
        if perm_str in user.denied_permissions:
            return False
        
        # 2. Explicit grant
        if perm_str in user.custom_permissions:
            return True
        
        # 3. Role-based permissions
        role_perms = self.role_permissions.get(user.role, set())
        if permission in role_perms:
            return True
        
        # 4. Admin always has all permissions
        if user.role == RoleType.ADMIN:
            return True
        
        return False
    
    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all effective permissions for a user"""
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return set()
        
        # Start with role permissions
        role_perms = {p.value for p in self.role_permissions.get(user.role, set())}
        
        # Add custom permissions
        role_perms.update(user.custom_permissions)
        
        # Remove denied permissions
        role_perms -= user.denied_permissions
        
        return role_perms
    
    def grant_permission(
        self,
        user_id: str,
        permission: PermissionType,
        admin_id: str,
    ) -> bool:
        """Grant additional permission to a user"""
        if not self.has_permission(admin_id, PermissionType.PERMISSION_MANAGE):
            raise PermissionError("Permission denied")
        
        user = self.users.get(user_id)
        if not user:
            return False
        
        user.custom_permissions.add(permission.value)
        user.denied_permissions.discard(permission.value)
        logger.info(f"Granted {permission.value} to {user.name}")
        return True
    
    def revoke_permission(
        self,
        user_id: str,
        permission: PermissionType,
        admin_id: str,
    ) -> bool:
        """Explicitly deny a permission from a user"""
        if not self.has_permission(admin_id, PermissionType.PERMISSION_MANAGE):
            raise PermissionError("Permission denied")
        
        user = self.users.get(user_id)
        if not user:
            return False
        
        user.denied_permissions.add(permission.value)
        user.custom_permissions.discard(permission.value)
        logger.info(f"Revoked {permission.value} from {user.name}")
        return True
    
    # ===========================================
    # DEVICE ASSIGNMENT
    # ===========================================
    
    def assign_device_to_room(
        self,
        device_id: str,
        device_name: str,
        room_id: str,
        entity_id: Optional[str] = None,
        is_high_risk: bool = False,
        admin_id: Optional[str] = None,
    ) -> DeviceAssignment:
        """Assign an IoT device to a room"""
        if admin_id and not self.has_permission(admin_id, PermissionType.DEVICE_MANAGE):
            raise PermissionError("Permission denied")
        
        assignment = DeviceAssignment(
            device_id=device_id,
            device_name=device_name,
            entity_id=entity_id,
            assigned_to_room=room_id,
            is_high_risk=is_high_risk,
        )
        
        self.device_assignments[device_id] = assignment
        
        if room_id in self.rooms:
            self.rooms[room_id].assigned_devices.append(device_id)
        
        logger.info(f"Assigned device {device_name} to room {room_id}")
        return assignment
    
    def assign_device_to_user(
        self,
        device_id: str,
        user_id: str,
        admin_id: Optional[str] = None,
    ) -> bool:
        """Grant a user direct access to a device"""
        if admin_id and not self.has_permission(admin_id, PermissionType.DEVICE_MANAGE):
            raise PermissionError("Permission denied")
        
        assignment = self.device_assignments.get(device_id)
        if not assignment:
            return False
        
        if user_id not in assignment.assigned_to_users:
            assignment.assigned_to_users.append(user_id)
        
        user = self.users.get(user_id)
        if user and device_id not in user.assigned_devices:
            user.assigned_devices.append(device_id)
        
        logger.info(f"Assigned device {device_id} to user {user_id}")
        return True
    
    def can_control_device(self, user_id: str, device_id: str) -> bool:
        """
        Check if a user can control a specific device
        
        Access granted if:
        1. User is admin (controls everything)
        2. Device is directly assigned to user
        3. Device is in user's assigned room
        4. User's role is in device's allowed_roles
        """
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False
        
        # Admin controls everything
        if user.role == RoleType.ADMIN:
            return True
        
        assignment = self.device_assignments.get(device_id)
        if not assignment:
            # Device not in system - check general device_control permission
            return self.has_permission(user_id, PermissionType.DEVICE_CONTROL)
        
        # Direct user assignment
        if user_id in assignment.assigned_to_users:
            return True
        
        # Device directly assigned to user
        if device_id in user.assigned_devices:
            return True
        
        # Room-based access
        if user.room_id and assignment.assigned_to_room == user.room_id:
            return True
        
        # Role-based access
        if user.role in assignment.allowed_roles:
            return True
        
        return False
    
    def get_user_devices(self, user_id: str) -> List[DeviceAssignment]:
        """Get all devices a user can control"""
        user = self.users.get(user_id)
        if not user:
            return []
        
        # Admin gets all devices
        if user.role == RoleType.ADMIN:
            return list(self.device_assignments.values())
        
        accessible = []
        for device_id, assignment in self.device_assignments.items():
            if self.can_control_device(user_id, device_id):
                accessible.append(assignment)
        
        return accessible
    
    # ===========================================
    # MESSAGING SYSTEM
    # ===========================================
    
    def send_message(
        self,
        sender_id: str,
        content: str,
        recipient_ids: Optional[List[str]] = None,
        message_type: str = "info",
        expires_hours: Optional[int] = None,
    ) -> NetworkMessage:
        """
        Send a message to users on the network
        
        Args:
            sender_id: ID of the sending user
            content: Message content
            recipient_ids: List of recipient IDs (None = broadcast to all)
            message_type: info, alert, warning, emergency
            expires_hours: Hours until message expires
        """
        sender = self.users.get(sender_id)
        if not sender:
            raise ValueError("Sender not found")
        
        # Check permissions
        if recipient_ids is None:
            # Broadcast
            if not self.has_permission(sender_id, PermissionType.BROADCAST_MESSAGE):
                raise PermissionError("Permission denied for broadcast")
        else:
            # Direct message
            if not self.has_permission(sender_id, PermissionType.DIRECT_MESSAGE):
                if not self.has_permission(sender_id, PermissionType.CHAT):
                    raise PermissionError("Permission denied for messaging")
        
        message = NetworkMessage(
            id=f"msg-{secrets.token_hex(4)}",
            sender_id=sender_id,
            sender_name=sender.name,
            recipient_ids=recipient_ids or [],
            content=content,
            message_type=message_type,
            expires_at=datetime.now() + timedelta(hours=expires_hours) if expires_hours else None,
        )
        
        self.messages.append(message)
        logger.info(f"Message sent from {sender.name}: {content[:50]}...")
        return message
    
    def get_messages_for_user(self, user_id: str, unread_only: bool = False) -> List[NetworkMessage]:
        """Get messages visible to a user"""
        now = datetime.now()
        visible = []
        
        for msg in self.messages:
            # Check expiry
            if msg.expires_at and msg.expires_at < now:
                continue
            
            # Broadcast or directed at user
            if not msg.recipient_ids or user_id in msg.recipient_ids:
                if unread_only and user_id in msg.read_by:
                    continue
                visible.append(msg)
        
        return sorted(visible, key=lambda m: m.created_at, reverse=True)
    
    def mark_message_read(self, user_id: str, message_id: str) -> bool:
        """Mark a message as read by a user"""
        for msg in self.messages:
            if msg.id == message_id:
                if user_id not in msg.read_by:
                    msg.read_by.append(user_id)
                return True
        return False
    
    def send_welcome_message(self, user_id: str) -> NetworkMessage:
        """Send a welcome message to a new user"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        room_info = ""
        if user.room_id and user.room_id in self.rooms:
            room = self.rooms[user.room_id]
            room_info = f" You've been assigned to {room.name}."
        
        content = f"""Welcome to the co-living space, {user.name}! 🏠

{room_info}

Here's what you can do:
• Control devices in your assigned areas
• Chat with the AI assistant for help
• {"Invite guests for temporary access" if user.role != RoleType.GUEST else "Contact a resident if you need extended access"}

If you need any help, just ask in the chat!"""
        
        return self.send_message(
            sender_id="admin-001",
            content=content,
            recipient_ids=[user_id],
            message_type="info",
        )
    
    # ===========================================
    # ROOM MANAGEMENT
    # ===========================================
    
    def get_room(self, room_id: str) -> Optional[RoomUnit]:
        """Get room by ID"""
        return self.rooms.get(room_id)
    
    def list_rooms(self) -> List[RoomUnit]:
        """List all rooms"""
        return list(self.rooms.values())
    
    def assign_user_to_room(self, user_id: str, room_id: str, admin_id: str) -> bool:
        """Assign a user to a room"""
        if not self.has_permission(admin_id, PermissionType.USER_MANAGE):
            raise PermissionError("Permission denied")
        
        user = self.users.get(user_id)
        room = self.rooms.get(room_id)
        
        if not user or not room:
            return False
        
        # Remove from old room
        if user.room_id and user.room_id in self.rooms:
            old_room = self.rooms[user.room_id]
            if user_id in old_room.current_occupants:
                old_room.current_occupants.remove(user_id)
        
        # Add to new room
        user.room_id = room_id
        if user_id not in room.current_occupants:
            room.current_occupants.append(user_id)
        
        logger.info(f"Assigned user {user.name} to {room.name}")
        return True
    
    # ===========================================
    # GUEST MANAGEMENT
    # ===========================================
    
    def invite_guest(
        self,
        inviter_id: str,
        guest_name: str,
        expiry_hours: int = 24,
        room_access: Optional[str] = None,
    ) -> NetworkUser:
        """
        Invite a guest to the network
        
        Residents can invite guests, guests get:
        - Limited device control
        - Chat access
        - Access to inviter's room (if specified)
        - Expiry after specified hours
        """
        inviter = self.users.get(inviter_id)
        if not inviter:
            raise ValueError("Inviter not found")
        
        if not self.has_permission(inviter_id, PermissionType.GUEST_INVITE):
            raise PermissionError("Permission denied")
        
        # Default to inviter's room if not specified
        room_id = room_access or inviter.room_id
        
        guest = self.create_user(
            name=guest_name,
            role=RoleType.GUEST,
            room_id=room_id,
            expiry_hours=expiry_hours,
            creator_id=inviter_id,
        )
        
        # Send welcome message
        self.send_welcome_message(guest.id)
        
        # Notify inviter
        self.send_message(
            sender_id="admin-001",
            content=f"Guest '{guest_name}' has been added. Their access expires in {expiry_hours} hours.",
            recipient_ids=[inviter_id],
            message_type="info",
        )
        
        return guest
    
    def revoke_guest(self, guest_id: str, admin_id: str) -> bool:
        """Revoke a guest's access"""
        if not self.has_permission(admin_id, PermissionType.GUEST_REVOKE):
            raise PermissionError("Permission denied")
        
        guest = self.users.get(guest_id)
        if not guest or guest.role != RoleType.GUEST:
            return False
        
        return self.deactivate_user(guest_id, admin_id)
    
    # ===========================================
    # SERIALIZATION
    # ===========================================
    
    def export_state(self) -> Dict[str, Any]:
        """Export RBAC state for backup/persistence"""
        return {
            "users": {uid: u.to_dict() for uid, u in self.users.items()},
            "rooms": {rid: {
                "id": r.id,
                "name": r.name,
                "floor": r.floor,
                "building": r.building,
                "assigned_devices": r.assigned_devices,
                "max_occupants": r.max_occupants,
                "current_occupants": r.current_occupants,
            } for rid, r in self.rooms.items()},
            "device_assignments": {did: {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "entity_id": d.entity_id,
                "assigned_to_room": d.assigned_to_room,
                "assigned_to_users": d.assigned_to_users,
                "is_high_risk": d.is_high_risk,
            } for did, d in self.device_assignments.items()},
            "messages": [m.to_dict() for m in self.messages[-100:]],  # Last 100 messages
        }


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_rbac_manager: Optional[RBACManager] = None

def get_rbac_manager() -> RBACManager:
    """Get the singleton RBAC manager"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
