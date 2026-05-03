"""
Bluetooth Pairing & Proximity Authentication Module
P5: BT1 - Bluetooth integration for admin proximity detection

Features:
- BT1.1-BT1.9: Full Bluetooth pairing system
- Admin phone pairing via BLE
- Proximity-based auto-unlock
- Guest temporary access via Bluetooth
- Fallback when Bluetooth unavailable
"""

import asyncio
import json
import logging
import hashlib
import secrets
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS & TYPES
# ============================================================================

class DeviceType(str, Enum):
    """Type of Bluetooth device"""
    ADMIN_PHONE = "admin_phone"
    FAMILY_PHONE = "family_phone"
    GUEST_DEVICE = "guest_device"
    IOT_DEVICE = "iot_device"
    UNKNOWN = "unknown"


class PairingStatus(str, Enum):
    """Status of pairing process"""
    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PAIRED = "paired"
    FAILED = "failed"
    EXPIRED = "expired"


class ProximityLevel(str, Enum):
    """Proximity based on RSSI signal strength"""
    IMMEDIATE = "immediate"   # < 1 meter, RSSI > -50
    NEAR = "near"             # 1-3 meters, RSSI -50 to -70
    FAR = "far"               # 3-10 meters, RSSI -70 to -90
    OUT_OF_RANGE = "out_of_range"  # > 10 meters or not detected


class BluetoothCapability(str, Enum):
    """Bluetooth capabilities of the host system"""
    FULL = "full"            # Full BLE support with bleak
    WEB_ONLY = "web_only"    # Web Bluetooth API only
    SIMULATED = "simulated"  # No hardware, simulated for testing
    UNAVAILABLE = "unavailable"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PairedDevice:
    """A paired Bluetooth device"""
    device_id: str
    name: str
    mac_address: str
    device_type: DeviceType
    user_id: Optional[str]
    paired_at: datetime
    last_seen: Optional[datetime] = None
    last_rssi: Optional[int] = None
    proximity: ProximityLevel = ProximityLevel.OUT_OF_RANGE
    is_trusted: bool = False
    permissions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "device_type": self.device_type.value,
            "proximity": self.proximity.value,
            "paired_at": self.paired_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }


@dataclass
class PairingSession:
    """Active pairing session"""
    session_id: str
    pin_code: str
    device_name: Optional[str]
    device_mac: Optional[str]
    status: PairingStatus
    created_at: datetime
    expires_at: datetime
    device_type: DeviceType = DeviceType.UNKNOWN
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class ProximityEvent:
    """Proximity detection event"""
    device_id: str
    old_proximity: ProximityLevel
    new_proximity: ProximityLevel
    rssi: int
    timestamp: datetime
    triggered_action: Optional[str] = None


# ============================================================================
# BLUETOOTH MANAGER
# ============================================================================

class BluetoothManager:
    """
    Manages Bluetooth pairing and proximity detection.
    Uses bleak library for BLE on Python backend.
    Provides Web Bluetooth API integration for browser.
    """
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.paired_devices_file = data_dir / "paired_devices.json"
        self.paired_devices: Dict[str, PairedDevice] = {}
        self.active_sessions: Dict[str, PairingSession] = {}
        self.proximity_callbacks: List[Callable[[ProximityEvent], None]] = []
        self.scanning = False
        self.capability = BluetoothCapability.SIMULATED
        self._scanner = None
        self._load_paired_devices()
        self._detect_capability()
    
    def _detect_capability(self):
        """Detect Bluetooth capability of the system"""
        try:
            import bleak
            self.capability = BluetoothCapability.FULL
            logger.info("Bluetooth: Full BLE support available (bleak)")
        except ImportError:
            logger.warning("Bluetooth: bleak not installed, using simulated mode")
            self.capability = BluetoothCapability.SIMULATED
    
    def _load_paired_devices(self):
        """Load paired devices from disk"""
        if self.paired_devices_file.exists():
            try:
                with open(self.paired_devices_file, "r") as f:
                    data = json.load(f)
                    for device_data in data:
                        device = PairedDevice(
                            device_id=device_data["device_id"],
                            name=device_data["name"],
                            mac_address=device_data["mac_address"],
                            device_type=DeviceType(device_data["device_type"]),
                            user_id=device_data.get("user_id"),
                            paired_at=datetime.fromisoformat(device_data["paired_at"]),
                            is_trusted=device_data.get("is_trusted", False),
                            permissions=device_data.get("permissions", [])
                        )
                        self.paired_devices[device.device_id] = device
                logger.info(f"Loaded {len(self.paired_devices)} paired Bluetooth devices")
            except Exception as e:
                logger.error(f"Failed to load paired devices: {e}")
    
    def _save_paired_devices(self):
        """Save paired devices to disk"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = [device.to_dict() for device in self.paired_devices.values()]
            with open(self.paired_devices_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save paired devices: {e}")
    
    # ========================================================================
    # PAIRING
    # ========================================================================
    
    def start_pairing_session(
        self, 
        device_type: DeviceType = DeviceType.UNKNOWN,
        timeout_seconds: int = 300
    ) -> PairingSession:
        """Start a new pairing session with PIN code"""
        session_id = secrets.token_urlsafe(16)
        pin_code = f"{secrets.randbelow(1000000):06d}"  # 6-digit PIN
        
        session = PairingSession(
            session_id=session_id,
            pin_code=pin_code,
            device_name=None,
            device_mac=None,
            status=PairingStatus.PENDING,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=timeout_seconds),
            device_type=device_type
        )
        
        self.active_sessions[session_id] = session
        logger.info(f"Started pairing session {session_id} with PIN {pin_code}")
        
        return session
    
    async def discover_devices(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """Discover nearby Bluetooth devices"""
        if self.capability == BluetoothCapability.SIMULATED:
            # Return simulated devices for testing
            return [
                {
                    "address": "AA:BB:CC:DD:EE:F1",
                    "name": "iPhone (Simulated)",
                    "rssi": -45
                },
                {
                    "address": "AA:BB:CC:DD:EE:F2", 
                    "name": "Android Phone (Simulated)",
                    "rssi": -62
                },
                {
                    "address": "AA:BB:CC:DD:EE:F3",
                    "name": "Smart Lock (Simulated)",
                    "rssi": -78
                }
            ]
        
        if self.capability == BluetoothCapability.FULL:
            try:
                from bleak import BleakScanner
                devices = await BleakScanner.discover(timeout=timeout)
                return [
                    {
                        "address": d.address,
                        "name": d.name or "Unknown Device",
                        "rssi": d.rssi
                    }
                    for d in devices
                ]
            except Exception as e:
                logger.error(f"BLE scan failed: {e}")
                return []
        
        return []
    
    def confirm_pairing(
        self,
        session_id: str,
        pin_code: str,
        device_name: str,
        device_mac: str,
        user_id: Optional[str] = None
    ) -> Optional[PairedDevice]:
        """Confirm pairing with PIN code"""
        session = self.active_sessions.get(session_id)
        
        if not session:
            logger.warning(f"Pairing session not found: {session_id}")
            return None
        
        if session.is_expired:
            session.status = PairingStatus.EXPIRED
            logger.warning(f"Pairing session expired: {session_id}")
            return None
        
        if session.pin_code != pin_code:
            session.status = PairingStatus.FAILED
            logger.warning(f"Invalid PIN for session {session_id}")
            return None
        
        # Create paired device
        device_id = hashlib.sha256(device_mac.encode()).hexdigest()[:16]
        
        device = PairedDevice(
            device_id=device_id,
            name=device_name,
            mac_address=device_mac,
            device_type=session.device_type,
            user_id=user_id,
            paired_at=datetime.now(),
            is_trusted=session.device_type == DeviceType.ADMIN_PHONE
        )
        
        # Set default permissions based on device type
        if session.device_type == DeviceType.ADMIN_PHONE:
            device.permissions = ["all"]
        elif session.device_type == DeviceType.FAMILY_PHONE:
            device.permissions = ["view", "control_own_room", "automation"]
        elif session.device_type == DeviceType.GUEST_DEVICE:
            device.permissions = ["view_limited"]
        
        self.paired_devices[device_id] = device
        self._save_paired_devices()
        
        session.status = PairingStatus.PAIRED
        del self.active_sessions[session_id]
        
        logger.info(f"Device paired successfully: {device_name} ({device_mac})")
        return device
    
    def unpair_device(self, device_id: str) -> bool:
        """Remove a paired device"""
        if device_id in self.paired_devices:
            device = self.paired_devices[device_id]
            del self.paired_devices[device_id]
            self._save_paired_devices()
            logger.info(f"Device unpaired: {device.name}")
            return True
        return False
    
    def get_paired_devices(self) -> List[PairedDevice]:
        """Get all paired devices"""
        return list(self.paired_devices.values())
    
    # ========================================================================
    # PROXIMITY DETECTION
    # ========================================================================
    
    def rssi_to_proximity(self, rssi: int) -> ProximityLevel:
        """Convert RSSI signal strength to proximity level"""
        if rssi > -50:
            return ProximityLevel.IMMEDIATE
        elif rssi > -70:
            return ProximityLevel.NEAR
        elif rssi > -90:
            return ProximityLevel.FAR
        else:
            return ProximityLevel.OUT_OF_RANGE
    
    def update_device_proximity(
        self, 
        device_id: str, 
        rssi: int
    ) -> Optional[ProximityEvent]:
        """Update device proximity and trigger callbacks if changed"""
        device = self.paired_devices.get(device_id)
        if not device:
            return None
        
        old_proximity = device.proximity
        new_proximity = self.rssi_to_proximity(rssi)
        
        device.last_seen = datetime.now()
        device.last_rssi = rssi
        device.proximity = new_proximity
        
        if old_proximity != new_proximity:
            event = ProximityEvent(
                device_id=device_id,
                old_proximity=old_proximity,
                new_proximity=new_proximity,
                rssi=rssi,
                timestamp=datetime.now()
            )
            
            # Trigger callbacks
            for callback in self.proximity_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Proximity callback error: {e}")
            
            logger.info(
                f"Device {device.name} proximity changed: "
                f"{old_proximity.value} -> {new_proximity.value} (RSSI: {rssi})"
            )
            
            return event
        
        return None
    
    def on_proximity_change(self, callback: Callable[[ProximityEvent], None]):
        """Register callback for proximity changes"""
        self.proximity_callbacks.append(callback)
    
    async def start_proximity_scanning(self, interval: float = 2.0):
        """Start continuous proximity scanning"""
        if self.scanning:
            return
        
        self.scanning = True
        logger.info("Started proximity scanning")
        
        while self.scanning:
            try:
                if self.capability == BluetoothCapability.FULL:
                    from bleak import BleakScanner
                    devices = await BleakScanner.discover(timeout=1.0)
                    
                    for d in devices:
                        # Check if this is a paired device
                        device_id = hashlib.sha256(d.address.encode()).hexdigest()[:16]
                        if device_id in self.paired_devices:
                            self.update_device_proximity(device_id, d.rssi)
                
                elif self.capability == BluetoothCapability.SIMULATED:
                    # Simulate proximity for testing
                    import random
                    for device_id, device in self.paired_devices.items():
                        if device.is_trusted:
                            # Simulate RSSI fluctuation
                            simulated_rssi = random.randint(-80, -40)
                            self.update_device_proximity(device_id, simulated_rssi)
                
            except Exception as e:
                logger.error(f"Proximity scan error: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_proximity_scanning(self):
        """Stop proximity scanning"""
        self.scanning = False
        logger.info("Stopped proximity scanning")
    
    # ========================================================================
    # PROXIMITY-BASED AUTHENTICATION
    # ========================================================================
    
    def is_admin_nearby(self) -> bool:
        """Check if any admin device is in immediate or near proximity"""
        for device in self.paired_devices.values():
            if device.device_type == DeviceType.ADMIN_PHONE:
                if device.proximity in [ProximityLevel.IMMEDIATE, ProximityLevel.NEAR]:
                    # Also check if recently seen (within 30 seconds)
                    if device.last_seen:
                        age = (datetime.now() - device.last_seen).total_seconds()
                        if age < 30:
                            return True
        return False
    
    def get_nearby_users(self) -> List[Dict[str, Any]]:
        """Get list of users whose devices are nearby"""
        nearby = []
        for device in self.paired_devices.values():
            if device.proximity in [ProximityLevel.IMMEDIATE, ProximityLevel.NEAR]:
                if device.last_seen:
                    age = (datetime.now() - device.last_seen).total_seconds()
                    if age < 30:
                        nearby.append({
                            "device_id": device.device_id,
                            "device_name": device.name,
                            "user_id": device.user_id,
                            "proximity": device.proximity.value,
                            "rssi": device.last_rssi
                        })
        return nearby
    
    def can_auto_unlock(self, required_proximity: ProximityLevel = ProximityLevel.IMMEDIATE) -> bool:
        """Check if auto-unlock should be allowed based on admin proximity"""
        for device in self.paired_devices.values():
            if device.device_type == DeviceType.ADMIN_PHONE and device.is_trusted:
                if required_proximity == ProximityLevel.IMMEDIATE:
                    if device.proximity == ProximityLevel.IMMEDIATE:
                        return True
                elif required_proximity == ProximityLevel.NEAR:
                    if device.proximity in [ProximityLevel.IMMEDIATE, ProximityLevel.NEAR]:
                        return True
        return False
    
    # ========================================================================
    # GUEST TEMPORARY ACCESS
    # ========================================================================
    
    def create_guest_access_token(
        self,
        guest_name: str,
        valid_hours: int = 24,
        permissions: List[str] = None
    ) -> Dict[str, Any]:
        """Create temporary Bluetooth access for a guest"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=valid_hours)
        
        guest_access = {
            "token": token,
            "guest_name": guest_name,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
            "permissions": permissions or ["view_limited"],
            "paired_device_id": None  # Set when guest pairs
        }
        
        # Store in guest access file
        guest_file = self.data_dir / "guest_access.json"
        guests = []
        if guest_file.exists():
            with open(guest_file) as f:
                guests = json.load(f)
        
        guests.append(guest_access)
        
        with open(guest_file, "w") as f:
            json.dump(guests, f, indent=2)
        
        logger.info(f"Created guest access for {guest_name}, expires in {valid_hours}h")
        
        return guest_access
    
    def validate_guest_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a guest access token"""
        guest_file = self.data_dir / "guest_access.json"
        if not guest_file.exists():
            return None
        
        with open(guest_file) as f:
            guests = json.load(f)
        
        for guest in guests:
            if guest["token"] == token:
                expires = datetime.fromisoformat(guest["expires_at"])
                if datetime.now() < expires:
                    return guest
                else:
                    logger.info(f"Guest token expired for {guest['guest_name']}")
        
        return None


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_bluetooth_manager: Optional[BluetoothManager] = None

def get_bluetooth_manager() -> BluetoothManager:
    """Get or create the global Bluetooth manager"""
    global _bluetooth_manager
    if _bluetooth_manager is None:
        _bluetooth_manager = BluetoothManager()
    return _bluetooth_manager


# ============================================================================
# API ROUTES
# ============================================================================

class StartPairingRequest(BaseModel):
    device_type: str = "unknown"
    timeout_seconds: int = 300


class ConfirmPairingRequest(BaseModel):
    session_id: str
    pin_code: str
    device_name: str
    device_mac: str
    user_id: Optional[str] = None


class CreateGuestAccessRequest(BaseModel):
    guest_name: str
    valid_hours: int = 24
    permissions: Optional[List[str]] = None


def create_bluetooth_routes() -> APIRouter:
    """Create FastAPI router for Bluetooth endpoints"""
    router = APIRouter(prefix="/bluetooth", tags=["bluetooth"])
    
    @router.get("/capability")
    async def get_capability():
        """Get Bluetooth capability of the system"""
        manager = get_bluetooth_manager()
        return {
            "capability": manager.capability.value,
            "paired_devices_count": len(manager.paired_devices),
            "scanning": manager.scanning
        }
    
    @router.get("/devices")
    async def list_paired_devices():
        """List all paired Bluetooth devices"""
        manager = get_bluetooth_manager()
        return {
            "devices": [d.to_dict() for d in manager.get_paired_devices()]
        }
    
    @router.post("/discover")
    async def discover_devices(timeout: float = 10.0):
        """Discover nearby Bluetooth devices"""
        manager = get_bluetooth_manager()
        devices = await manager.discover_devices(timeout)
        return {"devices": devices}
    
    @router.post("/pair/start")
    async def start_pairing(request: StartPairingRequest):
        """Start a new pairing session"""
        manager = get_bluetooth_manager()
        device_type = DeviceType(request.device_type)
        session = manager.start_pairing_session(device_type, request.timeout_seconds)
        return {
            "session_id": session.session_id,
            "pin_code": session.pin_code,
            "expires_at": session.expires_at.isoformat(),
            "status": session.status.value
        }
    
    @router.post("/pair/confirm")
    async def confirm_pairing(request: ConfirmPairingRequest):
        """Confirm pairing with PIN code"""
        manager = get_bluetooth_manager()
        device = manager.confirm_pairing(
            session_id=request.session_id,
            pin_code=request.pin_code,
            device_name=request.device_name,
            device_mac=request.device_mac,
            user_id=request.user_id
        )
        
        if device:
            return {"success": True, "device": device.to_dict()}
        else:
            raise HTTPException(status_code=400, detail="Pairing failed")
    
    @router.delete("/devices/{device_id}")
    async def unpair_device(device_id: str):
        """Remove a paired device"""
        manager = get_bluetooth_manager()
        success = manager.unpair_device(device_id)
        if success:
            return {"success": True}
        raise HTTPException(status_code=404, detail="Device not found")
    
    @router.get("/proximity")
    async def get_proximity_status():
        """Get current proximity status of paired devices"""
        manager = get_bluetooth_manager()
        return {
            "admin_nearby": manager.is_admin_nearby(),
            "can_auto_unlock": manager.can_auto_unlock(),
            "nearby_users": manager.get_nearby_users()
        }
    
    @router.post("/proximity/start")
    async def start_proximity_scanning():
        """Start continuous proximity scanning"""
        manager = get_bluetooth_manager()
        asyncio.create_task(manager.start_proximity_scanning())
        return {"success": True, "message": "Proximity scanning started"}
    
    @router.post("/proximity/stop")
    async def stop_proximity_scanning():
        """Stop proximity scanning"""
        manager = get_bluetooth_manager()
        manager.stop_proximity_scanning()
        return {"success": True, "message": "Proximity scanning stopped"}
    
    @router.post("/guest/create")
    async def create_guest_access(request: CreateGuestAccessRequest):
        """Create temporary guest access"""
        manager = get_bluetooth_manager()
        access = manager.create_guest_access_token(
            guest_name=request.guest_name,
            valid_hours=request.valid_hours,
            permissions=request.permissions
        )
        return access
    
    @router.get("/guest/validate/{token}")
    async def validate_guest_token(token: str):
        """Validate a guest access token"""
        manager = get_bluetooth_manager()
        access = manager.validate_guest_token(token)
        if access:
            return {"valid": True, "access": access}
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return router


# ============================================================================
# WEB BLUETOOTH INTEGRATION
# ============================================================================

WEB_BLUETOOTH_JS = """
// Web Bluetooth API integration for Local Home Agent
// Include this in the browser for client-side pairing

class LocalAgentBluetooth {
    constructor(apiBase = '') {
        this.apiBase = apiBase;
        this.device = null;
        this.isConnected = false;
    }
    
    async checkSupport() {
        if (!navigator.bluetooth) {
            return { supported: false, reason: 'Web Bluetooth API not available' };
        }
        return { supported: true };
    }
    
    async requestDevice() {
        try {
            this.device = await navigator.bluetooth.requestDevice({
                acceptAllDevices: true,
                optionalServices: ['battery_service', 'device_information']
            });
            
            this.device.addEventListener('gattserverdisconnected', () => {
                this.isConnected = false;
                console.log('Bluetooth device disconnected');
            });
            
            return {
                name: this.device.name,
                id: this.device.id
            };
        } catch (error) {
            console.error('Bluetooth request failed:', error);
            throw error;
        }
    }
    
    async startPairing(deviceType = 'admin_phone') {
        // 1. Request device from browser
        const device = await this.requestDevice();
        
        // 2. Start pairing session on server
        const response = await fetch(`${this.apiBase}/bluetooth/pair/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_type: deviceType })
        });
        
        const session = await response.json();
        
        return {
            device,
            session,
            pinCode: session.pin_code
        };
    }
    
    async confirmPairing(sessionId, pinCode) {
        if (!this.device) {
            throw new Error('No device selected');
        }
        
        const response = await fetch(`${this.apiBase}/bluetooth/pair/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                pin_code: pinCode,
                device_name: this.device.name || 'Unknown Device',
                device_mac: this.device.id // Web Bluetooth uses ID, not MAC
            })
        });
        
        return await response.json();
    }
    
    async getProximityStatus() {
        const response = await fetch(`${this.apiBase}/bluetooth/proximity`);
        return await response.json();
    }
}

// Export for use
window.LocalAgentBluetooth = LocalAgentBluetooth;
"""


def get_web_bluetooth_js() -> str:
    """Get the Web Bluetooth JavaScript code"""
    return WEB_BLUETOOTH_JS
