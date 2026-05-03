"""
Multi-Channel Notification Service - WiFi & Bluetooth Push to Mobile Admin
Implements adaptive delivery channels for co-living property management

Architecture Rationale:
=======================

WiFi-First Strategy (Primary Channel):
--------------------------------------
1. **Latency**: 10-50ms typical, suitable for real-time alerts
2. **Range**: Entire property coverage via existing AP infrastructure
3. **Bandwidth**: Supports rich media (images, callable UI JSON)
4. **Always-On**: Persistent WebSocket connections for instant push
5. **Multi-Device**: Admin can receive on phone, tablet, desktop simultaneously

Bluetooth LE Fallback (Secondary Channel):
------------------------------------------
1. **Network Independence**: Works when WiFi is down or router fails
2. **Proximity Awareness**: Automatically escalates when admin is physically near
3. **Ultra-Low Power**: Admin phone battery-friendly for continuous scanning
4. **Mesh Capability**: BLE mesh can relay through resident devices if needed
5. **Secure Pairing**: Uses device-specific keys, not network credentials

Hybrid Delivery Decision Tree:
------------------------------
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Notification Event Triggered                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Is admin connected via WebSocket?                                           │
│  YES ────► Push via WiFi WebSocket (instant, 10ms)                          │
│  NO  ────► Continue to fallback chain                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Is admin phone registered for push?                                         │
│  YES ────► Send via Web Push / Firebase Cloud Messaging                     │
│  NO  ────► Continue to BLE fallback                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Is admin phone in BLE range (paired)?                                       │
│  YES ────► Push via Bluetooth LE characteristic write                       │
│  NO  ────► Queue for retry + send email as last resort                      │
└─────────────────────────────────────────────────────────────────────────────┘

Energy Model Integration:
-------------------------
- LOW energy events (device status): WiFi only, no retry
- MEDIUM energy events (guest arrivals): WiFi + Web Push
- HIGH energy events (security alerts): All channels + retry until ACK
- CRITICAL events (safety/emergency): All channels + escalation chain

Mobile Sector Considerations:
-----------------------------
1. **iOS**: Web Push requires PWA installation; BLE works via Core Bluetooth
2. **Android**: FCM for background push; BLE via standard Android Bluetooth stack
3. **Cross-Platform**: VAPID-based Web Push works on both (Chrome, Safari, Firefox)
4. **Battery Impact**: BLE beacons are ultra-low power; Web Push uses system socket
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any, Callable, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Maps to energy model levels"""
    LOW = "low"           # Device status, routine updates
    MEDIUM = "medium"     # Guest arrivals, schedule changes
    HIGH = "high"         # Security alerts, failed verifications
    CRITICAL = "critical" # Safety/emergency, system failures


class DeliveryChannel(Enum):
    """Available notification delivery channels"""
    WEBSOCKET = "websocket"     # WiFi - real-time push
    WEB_PUSH = "web_push"       # WiFi - background push (VAPID)
    BLUETOOTH = "bluetooth"     # BLE - proximity-based
    EMAIL = "email"             # Last resort fallback
    SMS = "sms"                 # Optional - high priority only


@dataclass
class NotificationPayload:
    """Structured notification data"""
    id: str
    title: str
    body: str
    priority: NotificationPriority
    category: str  # "security", "device", "guest", "system"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    requires_ack: bool = False
    ttl_seconds: int = 3600  # Time to live
    callable_ui: Optional[Dict] = None  # Inline action UI
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.value,
            "category": self.category,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "requires_ack": self.requires_ack,
            "callable_ui": self.callable_ui
        }


@dataclass
class DeliveryResult:
    """Result of a delivery attempt"""
    channel: DeliveryChannel
    success: bool
    recipient: str
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class AdminDevice:
    """Registered admin device for notifications"""
    device_id: str
    user_id: str
    device_name: str
    platform: str  # "ios", "android", "web"
    push_token: Optional[str] = None  # FCM/APNS token
    vapid_subscription: Optional[Dict] = None  # Web Push subscription
    bluetooth_address: Optional[str] = None  # BLE MAC for proximity
    websocket_connected: bool = False
    last_seen: datetime = field(default_factory=datetime.now)


class NotificationService:
    """
    Multi-channel notification service for co-living admin alerts.
    
    Implements WiFi-first strategy with BLE fallback for mobile admins.
    Integrates with the thermodynamic energy model for priority escalation.
    """
    
    def __init__(self):
        self._admin_devices: Dict[str, AdminDevice] = {}
        self._websocket_connections: Dict[str, Any] = {}  # user_id -> WebSocket
        self._pending_notifications: List[NotificationPayload] = []
        self._delivery_log: List[DeliveryResult] = []
        self._handlers: Dict[DeliveryChannel, Callable] = {}
        self._ble_client = None  # BluetoothPairingManager instance
        
        # VAPID keys for Web Push (generated once, stored)
        self._vapid_private_key: Optional[str] = None
        self._vapid_public_key: Optional[str] = None
        
        # Retry configuration
        self._max_retries = 3
        self._retry_delays = [5, 30, 120]  # seconds
        
        # Load config
        self._load_config()
    
    def _load_config(self):
        """Load notification config from file"""
        config_path = Path("config/notifications.json")
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                self._vapid_private_key = config.get("vapid_private_key")
                self._vapid_public_key = config.get("vapid_public_key")
                
                # Load registered devices
                for device_data in config.get("admin_devices", []):
                    device = AdminDevice(**device_data)
                    self._admin_devices[device.device_id] = device
                    
            except Exception as e:
                logger.error(f"Failed to load notification config: {e}")
    
    def _save_config(self):
        """Persist notification config"""
        config_path = Path("config/notifications.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = {
            "vapid_private_key": self._vapid_private_key,
            "vapid_public_key": self._vapid_public_key,
            "admin_devices": [
                {
                    "device_id": d.device_id,
                    "user_id": d.user_id,
                    "device_name": d.device_name,
                    "platform": d.platform,
                    "push_token": d.push_token,
                    "vapid_subscription": d.vapid_subscription,
                    "bluetooth_address": d.bluetooth_address,
                }
                for d in self._admin_devices.values()
            ]
        }
        
        config_path.write_text(json.dumps(config, indent=2))
    
    # -------------------------------------------------------------------------
    # Channel Registration
    # -------------------------------------------------------------------------
    
    def register_admin_device(self, device: AdminDevice) -> bool:
        """Register an admin device for push notifications"""
        self._admin_devices[device.device_id] = device
        self._save_config()
        logger.info(f"Registered admin device: {device.device_name} ({device.platform})")
        return True
    
    def register_websocket(self, user_id: str, websocket: Any) -> None:
        """Register a WebSocket connection for real-time push"""
        self._websocket_connections[user_id] = websocket
        
        # Update device status
        for device in self._admin_devices.values():
            if device.user_id == user_id:
                device.websocket_connected = True
                device.last_seen = datetime.now()
        
        logger.info(f"WebSocket registered for admin: {user_id}")
    
    def unregister_websocket(self, user_id: str) -> None:
        """Unregister a WebSocket connection"""
        self._websocket_connections.pop(user_id, None)
        
        for device in self._admin_devices.values():
            if device.user_id == user_id:
                device.websocket_connected = False
    
    def register_vapid_subscription(
        self, 
        device_id: str, 
        subscription: Dict
    ) -> bool:
        """Register Web Push (VAPID) subscription for a device"""
        if device_id in self._admin_devices:
            self._admin_devices[device_id].vapid_subscription = subscription
            self._save_config()
            return True
        return False
    
    def register_bluetooth_device(
        self, 
        device_id: str, 
        bluetooth_address: str
    ) -> bool:
        """Register Bluetooth address for proximity notifications"""
        if device_id in self._admin_devices:
            self._admin_devices[device_id].bluetooth_address = bluetooth_address
            self._save_config()
            return True
        return False
    
    # -------------------------------------------------------------------------
    # Notification Sending
    # -------------------------------------------------------------------------
    
    async def send(
        self, 
        notification: NotificationPayload,
        target_users: Optional[List[str]] = None
    ) -> List[DeliveryResult]:
        """
        Send notification using adaptive channel selection.
        
        Priority-based channel escalation:
        - LOW: WebSocket only
        - MEDIUM: WebSocket + Web Push
        - HIGH: All WiFi channels + BLE if nearby
        - CRITICAL: All channels + retry until ACK
        """
        results: List[DeliveryResult] = []
        
        # Determine target devices
        target_devices = list(self._admin_devices.values())
        if target_users:
            target_devices = [
                d for d in target_devices 
                if d.user_id in target_users
            ]
        
        if not target_devices:
            logger.warning("No target devices for notification")
            return results
        
        for device in target_devices:
            device_results = await self._send_to_device(notification, device)
            results.extend(device_results)
        
        # Log delivery
        self._delivery_log.extend(results)
        
        # Handle retries for critical notifications
        if notification.requires_ack or notification.priority == NotificationPriority.CRITICAL:
            await self._schedule_retry(notification, results)
        
        return results
    
    async def _send_to_device(
        self, 
        notification: NotificationPayload, 
        device: AdminDevice
    ) -> List[DeliveryResult]:
        """Send notification to a single device using appropriate channels"""
        results: List[DeliveryResult] = []
        
        # Channel selection based on priority
        channels = self._select_channels(notification.priority, device)
        
        for channel in channels:
            result = await self._deliver(channel, notification, device)
            results.append(result)
            
            # Stop on first success for low priority
            if result.success and notification.priority == NotificationPriority.LOW:
                break
        
        return results
    
    def _select_channels(
        self, 
        priority: NotificationPriority, 
        device: AdminDevice
    ) -> List[DeliveryChannel]:
        """Select delivery channels based on priority and device capabilities"""
        channels = []
        
        # Always try WebSocket first if connected (fastest)
        if device.websocket_connected:
            channels.append(DeliveryChannel.WEBSOCKET)
        
        # Web Push for medium+ priority
        if priority.value in ["medium", "high", "critical"]:
            if device.vapid_subscription:
                channels.append(DeliveryChannel.WEB_PUSH)
        
        # BLE for high+ priority and if device is nearby
        if priority.value in ["high", "critical"]:
            if device.bluetooth_address:
                channels.append(DeliveryChannel.BLUETOOTH)
        
        # Email as last resort
        if priority == NotificationPriority.CRITICAL:
            channels.append(DeliveryChannel.EMAIL)
        
        return channels
    
    async def _deliver(
        self, 
        channel: DeliveryChannel, 
        notification: NotificationPayload,
        device: AdminDevice
    ) -> DeliveryResult:
        """Deliver notification via specific channel"""
        start = asyncio.get_event_loop().time()
        
        try:
            if channel == DeliveryChannel.WEBSOCKET:
                success = await self._send_websocket(notification, device)
            elif channel == DeliveryChannel.WEB_PUSH:
                success = await self._send_web_push(notification, device)
            elif channel == DeliveryChannel.BLUETOOTH:
                success = await self._send_bluetooth(notification, device)
            elif channel == DeliveryChannel.EMAIL:
                success = await self._send_email(notification, device)
            else:
                success = False
            
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return DeliveryResult(
                channel=channel,
                success=success,
                recipient=device.user_id,
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"Delivery failed for {channel.value}: {e}")
            return DeliveryResult(
                channel=channel,
                success=False,
                recipient=device.user_id,
                error=str(e)
            )
    
    # -------------------------------------------------------------------------
    # Channel Implementations
    # -------------------------------------------------------------------------
    
    async def _send_websocket(
        self, 
        notification: NotificationPayload, 
        device: AdminDevice
    ) -> bool:
        """Send via WiFi WebSocket (primary channel)"""
        ws = self._websocket_connections.get(device.user_id)
        if not ws:
            return False
        
        try:
            await ws.send_json({
                "type": "notification",
                "payload": notification.to_dict()
            })
            logger.info(f"WebSocket notification sent to {device.user_id}")
            return True
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            self.unregister_websocket(device.user_id)
            return False
    
    async def _send_web_push(
        self, 
        notification: NotificationPayload, 
        device: AdminDevice
    ) -> bool:
        """
        Send via Web Push (VAPID) - works on iOS Safari, Chrome, Firefox
        
        This enables background notifications when the admin app is closed.
        Requires HTTPS and service worker registration on the client.
        """
        if not device.vapid_subscription or not self._vapid_private_key:
            return False
        
        try:
            # Import py_vapid for Web Push
            # pip install pywebpush
            from pywebpush import webpush, WebPushException
            
            payload = json.dumps({
                "title": notification.title,
                "body": notification.body,
                "data": notification.data,
                "icon": "/static/icons/icon-192.png",
                "badge": "/static/icons/badge-72.png",
                "tag": notification.id,
                "requireInteraction": notification.requires_ack
            })
            
            webpush(
                subscription_info=device.vapid_subscription,
                data=payload,
                vapid_private_key=self._vapid_private_key,
                vapid_claims={
                    "sub": "mailto:admin@coliving.local"
                }
            )
            
            logger.info(f"Web Push sent to {device.device_name}")
            return True
            
        except ImportError:
            logger.warning("pywebpush not installed - Web Push disabled")
            return False
        except Exception as e:
            logger.error(f"Web Push failed: {e}")
            return False
    
    async def _send_bluetooth(
        self, 
        notification: NotificationPayload, 
        device: AdminDevice
    ) -> bool:
        """
        Send via Bluetooth LE - for proximity-based delivery
        
        Uses BLE characteristic write to push notification to nearby admin phone.
        The admin phone must have the companion app running in background
        scanning for our BLE service UUID.
        
        Advantages:
        - Works when WiFi is down
        - No internet required
        - Automatic proximity detection
        - Ultra-low power on modern phones
        """
        if not device.bluetooth_address:
            return False
        
        try:
            # Import Bluetooth client
            from .bluetooth_pairing import BluetoothPairingManager
            
            if self._ble_client is None:
                self._ble_client = BluetoothPairingManager()
            
            # BLE notification characteristic
            # Service UUID: home-agent-notifications
            NOTIFICATION_SERVICE_UUID = "00001810-0000-1000-8000-00805f9b34fb"
            NOTIFICATION_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"
            
            # Compact payload for BLE (max ~512 bytes)
            compact_payload = json.dumps({
                "t": notification.title[:50],
                "b": notification.body[:100],
                "p": notification.priority.value[0],  # l/m/h/c
                "c": notification.category,
                "id": notification.id[:8]
            })
            
            # This would use the platform's BLE stack
            # On Windows: bleak library
            # On Linux: bluepy or bleak
            # On macOS: bleak with CoreBluetooth
            
            # Placeholder - actual implementation in bluetooth_pairing.py
            success = await self._ble_client.send_notification(
                device.bluetooth_address,
                NOTIFICATION_CHAR_UUID,
                compact_payload.encode()
            )
            
            if success:
                logger.info(f"BLE notification sent to {device.device_name}")
            return success
            
        except ImportError:
            logger.warning("Bluetooth module not available")
            return False
        except Exception as e:
            logger.error(f"BLE notification failed: {e}")
            return False
    
    async def _send_email(
        self, 
        notification: NotificationPayload, 
        device: AdminDevice
    ) -> bool:
        """
        Send via email - last resort fallback
        
        Used for CRITICAL notifications when all real-time channels fail.
        """
        try:
            import aiosmtplib
            from email.message import EmailMessage
            
            # Load SMTP config
            config_path = Path("config/smtp.json")
            if not config_path.exists():
                logger.warning("SMTP not configured")
                return False
            
            smtp_config = json.loads(config_path.read_text())
            
            msg = EmailMessage()
            msg["Subject"] = f"[{notification.priority.value.upper()}] {notification.title}"
            msg["From"] = smtp_config.get("from_email", "agent@coliving.local")
            msg["To"] = smtp_config.get("admin_email")
            
            msg.set_content(f"""
{notification.title}
{'=' * len(notification.title)}

{notification.body}

Priority: {notification.priority.value.upper()}
Category: {notification.category}
Time: {notification.timestamp.isoformat()}

---
This is an automated message from your Local Home Agent.
            """)
            
            await aiosmtplib.send(
                msg,
                hostname=smtp_config.get("host", "localhost"),
                port=smtp_config.get("port", 587),
                username=smtp_config.get("username"),
                password=smtp_config.get("password"),
                use_tls=smtp_config.get("use_tls", True)
            )
            
            logger.info(f"Email notification sent for {notification.id}")
            return True
            
        except ImportError:
            logger.warning("aiosmtplib not installed - email disabled")
            return False
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
    
    # -------------------------------------------------------------------------
    # Retry Logic
    # -------------------------------------------------------------------------
    
    async def _schedule_retry(
        self, 
        notification: NotificationPayload,
        results: List[DeliveryResult]
    ) -> None:
        """Schedule retry for failed critical notifications"""
        # Check if any delivery succeeded
        if any(r.success for r in results):
            return
        
        # Add to pending
        self._pending_notifications.append(notification)
        
        # Schedule retry task
        asyncio.create_task(self._retry_notification(notification))
    
    async def _retry_notification(self, notification: NotificationPayload) -> None:
        """Retry sending a notification with exponential backoff"""
        for attempt, delay in enumerate(self._retry_delays):
            await asyncio.sleep(delay)
            
            # Check if notification was acknowledged
            if notification.id not in [n.id for n in self._pending_notifications]:
                return
            
            logger.info(f"Retrying notification {notification.id} (attempt {attempt + 2})")
            
            results = await self.send(notification)
            if any(r.success for r in results):
                self._pending_notifications = [
                    n for n in self._pending_notifications 
                    if n.id != notification.id
                ]
                return
        
        logger.error(f"All retries exhausted for notification {notification.id}")
    
    def acknowledge(self, notification_id: str) -> bool:
        """Acknowledge receipt of a notification"""
        before = len(self._pending_notifications)
        self._pending_notifications = [
            n for n in self._pending_notifications 
            if n.id != notification_id
        ]
        return len(self._pending_notifications) < before
    
    # -------------------------------------------------------------------------
    # Integration Helpers
    # -------------------------------------------------------------------------
    
    async def notify_security_event(
        self,
        level: str,  # "HIGH" or "CRITICAL"
        action: str,
        user_id: str,
        details: Dict[str, Any]
    ) -> List[DeliveryResult]:
        """
        Send security event notification - integrates with energy_model.py
        
        Called when energy model detects a high-energy action that requires
        admin awareness.
        """
        priority = (
            NotificationPriority.CRITICAL 
            if level == "CRITICAL" 
            else NotificationPriority.HIGH
        )
        
        notification = NotificationPayload(
            id=hashlib.md5(
                f"{datetime.now().isoformat()}{action}{user_id}".encode()
            ).hexdigest()[:12],
            title=f"Security Alert: {action}",
            body=f"User {user_id} attempted: {action}",
            priority=priority,
            category="security",
            data=details,
            requires_ack=level == "CRITICAL",
            callable_ui={
                "type": "ActionConfirmation",
                "data": {
                    "action": action,
                    "target": details.get("target", "Unknown"),
                    "message": f"Review security event from {user_id}",
                    "actionId": f"security_{datetime.now().timestamp():.0f}",
                    "energyLevel": details.get("energy", 0)
                }
            }
        )
        
        return await self.send(notification)
    
    async def notify_guest_arrival(
        self,
        guest_name: str,
        device_name: str,
        mac_address: str
    ) -> List[DeliveryResult]:
        """Send guest arrival notification"""
        notification = NotificationPayload(
            id=hashlib.md5(f"guest_{mac_address}".encode()).hexdigest()[:12],
            title="New Guest Arrived",
            body=f"{guest_name} connected via {device_name}",
            priority=NotificationPriority.MEDIUM,
            category="guest",
            data={
                "guest_name": guest_name,
                "device": device_name,
                "mac": mac_address
            },
            callable_ui={
                "type": "SceneSelector",
                "data": {
                    "title": "Quick Actions",
                    "scenes": [
                        {"id": "admit", "name": "Admit Guest", "icon": "✅"},
                        {"id": "deny", "name": "Deny Access", "icon": "❌"},
                        {"id": "verify", "name": "Request Verification", "icon": "🔐"}
                    ]
                }
            }
        )
        
        return await self.send(notification)
    
    async def notify_device_alert(
        self,
        device_name: str,
        alert_type: str,
        message: str
    ) -> List[DeliveryResult]:
        """Send device alert notification"""
        priority = (
            NotificationPriority.HIGH 
            if "offline" in alert_type.lower() or "error" in alert_type.lower()
            else NotificationPriority.LOW
        )
        
        notification = NotificationPayload(
            id=hashlib.md5(f"device_{device_name}_{alert_type}".encode()).hexdigest()[:12],
            title=f"Device: {alert_type}",
            body=f"{device_name}: {message}",
            priority=priority,
            category="device",
            data={
                "device": device_name,
                "alert_type": alert_type,
                "message": message
            }
        )
        
        return await self.send(notification)


# -------------------------------------------------------------------------
# Singleton instance
# -------------------------------------------------------------------------

_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the singleton notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# -------------------------------------------------------------------------
# FastAPI Integration
# -------------------------------------------------------------------------

def create_notification_routes(app):
    """Register notification API routes with FastAPI app"""
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect
    
    router = APIRouter(prefix="/api/notifications", tags=["notifications"])
    service = get_notification_service()
    
    @router.post("/register")
    async def register_device(
        device_id: str,
        user_id: str,
        device_name: str,
        platform: str,
        push_token: Optional[str] = None,
        bluetooth_address: Optional[str] = None
    ):
        """Register a device for push notifications"""
        device = AdminDevice(
            device_id=device_id,
            user_id=user_id,
            device_name=device_name,
            platform=platform,
            push_token=push_token,
            bluetooth_address=bluetooth_address
        )
        success = service.register_admin_device(device)
        return {"success": success}
    
    @router.post("/subscribe/push")
    async def subscribe_web_push(device_id: str, subscription: Dict):
        """Register Web Push subscription"""
        success = service.register_vapid_subscription(device_id, subscription)
        return {"success": success}
    
    @router.post("/acknowledge/{notification_id}")
    async def acknowledge_notification(notification_id: str):
        """Acknowledge receipt of a notification"""
        success = service.acknowledge(notification_id)
        return {"success": success}
    
    @router.get("/pending")
    async def get_pending():
        """Get pending notifications awaiting acknowledgment"""
        return {
            "pending": [n.to_dict() for n in service._pending_notifications]
        }
    
    @router.get("/history")
    async def get_history(limit: int = 50):
        """Get recent delivery history"""
        return {
            "history": [
                {
                    "channel": r.channel.value,
                    "success": r.success,
                    "recipient": r.recipient,
                    "timestamp": r.timestamp.isoformat(),
                    "latency_ms": r.latency_ms,
                    "error": r.error
                }
                for r in service._delivery_log[-limit:]
            ]
        }
    
    @router.websocket("/ws/{user_id}")
    async def notification_websocket(websocket: WebSocket, user_id: str):
        """WebSocket for real-time admin notifications"""
        await websocket.accept()
        service.register_websocket(user_id, websocket)
        
        try:
            while True:
                # Keep connection alive, handle pings
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            service.unregister_websocket(user_id)
    
    app.include_router(router)
    return router
