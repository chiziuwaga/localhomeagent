"""
IoT Device Pairing Wizard (P4 D2.3)
Guided device pairing with discovery, configuration, and testing
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import secrets

logger = logging.getLogger(__name__)


class DeviceCategory(Enum):
    """Categories of IoT devices"""
    LIGHTING = "lighting"
    CLIMATE = "climate"
    SECURITY = "security"
    ENTERTAINMENT = "entertainment"
    APPLIANCE = "appliance"
    SENSOR = "sensor"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    OTHER = "other"


class ConnectionType(Enum):
    """Device connection types"""
    WIFI = "wifi"
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    BLUETOOTH = "bluetooth"
    MATTER = "matter"
    THREAD = "thread"
    LOCAL_API = "local_api"
    CLOUD_API = "cloud_api"


class PairingStatus(Enum):
    """Status of pairing process"""
    NOT_STARTED = "not_started"
    DISCOVERING = "discovering"
    FOUND = "found"
    CONFIGURING = "configuring"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DiscoveredDevice:
    """A discovered but not yet paired device"""
    id: str
    name: str
    manufacturer: str
    model: Optional[str]
    category: DeviceCategory
    connection_type: ConnectionType
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    signal_strength: Optional[int] = None
    firmware_version: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "category": self.category.value,
            "connection_type": self.connection_type.value,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "signal_strength": self.signal_strength,
            "firmware_version": self.firmware_version,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }


@dataclass
class PairingStep:
    """A step in the pairing wizard"""
    id: str
    title: str
    description: str
    type: str  # "info", "input", "action", "test", "confirm"
    required: bool = True
    completed: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    validation: Optional[Callable[[Any], bool]] = None
    user_input: Any = None


@dataclass 
class PairingSession:
    """An active device pairing session"""
    id: str
    device: DiscoveredDevice
    user_id: str
    created_at: datetime
    status: PairingStatus = PairingStatus.NOT_STARTED
    current_step: int = 0
    steps: List[PairingStep] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device": self.device.to_dict(),
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": len(self.steps),
            "steps": [
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "type": s.type,
                    "completed": s.completed
                }
                for s in self.steps
            ],
            "error_message": self.error_message
        }


class PairingWizardTemplates:
    """Templates for different device types"""
    
    @staticmethod
    def get_steps_for_device(device: DiscoveredDevice) -> List[PairingStep]:
        """Get pairing steps based on device type"""
        
        # Common initial steps
        steps = [
            PairingStep(
                id="welcome",
                title="Device Found",
                description=f"Found {device.name} from {device.manufacturer}",
                type="info",
                data={"device_info": device.to_dict()}
            ),
            PairingStep(
                id="confirm_device",
                title="Confirm Device",
                description="Is this the device you want to pair?",
                type="confirm"
            )
        ]
        
        # Connection-specific steps
        if device.connection_type == ConnectionType.WIFI:
            steps.extend([
                PairingStep(
                    id="wifi_connect",
                    title="Connect to Device",
                    description="Device should be in pairing mode (usually blinking LED)",
                    type="action",
                    data={"instruction": "Press and hold the pairing button for 5 seconds"}
                ),
                PairingStep(
                    id="wifi_credentials",
                    title="WiFi Setup",
                    description="Enter your WiFi credentials to configure the device",
                    type="input",
                    data={"fields": ["ssid", "password"]}
                )
            ])
        elif device.connection_type == ConnectionType.ZIGBEE:
            steps.append(PairingStep(
                id="zigbee_pairing",
                title="Zigbee Pairing",
                description="Put your Zigbee coordinator in pairing mode and trigger the device",
                type="action",
                data={"timeout": 60}
            ))
        elif device.connection_type == ConnectionType.BLUETOOTH:
            steps.append(PairingStep(
                id="bluetooth_pair",
                title="Bluetooth Pairing",
                description="Enable Bluetooth on the device and accept the pairing request",
                type="action"
            ))
        elif device.connection_type == ConnectionType.MATTER:
            steps.extend([
                PairingStep(
                    id="matter_code",
                    title="Enter Matter Code",
                    description="Enter the 11-digit Matter pairing code from the device",
                    type="input",
                    data={"fields": ["pairing_code"], "format": "XXX-XXXX-XXX"}
                ),
                PairingStep(
                    id="matter_commission",
                    title="Commissioning",
                    description="Adding device to the Matter fabric...",
                    type="action"
                )
            ])
        
        # Category-specific configuration
        if device.category == DeviceCategory.LIGHTING:
            steps.append(PairingStep(
                id="light_config",
                title="Light Configuration",
                description="Configure your light settings",
                type="input",
                data={
                    "fields": ["default_brightness", "color_temp", "room"],
                    "options": {
                        "default_brightness": list(range(10, 110, 10)),
                        "color_temp": ["warm", "neutral", "cool", "daylight"],
                        "room": ["Living Room", "Bedroom", "Kitchen", "Bathroom", "Office", "Other"]
                    }
                }
            ))
        elif device.category == DeviceCategory.CLIMATE:
            steps.append(PairingStep(
                id="climate_config",
                title="Thermostat Configuration",
                description="Set up your climate preferences",
                type="input",
                data={
                    "fields": ["temp_unit", "default_heat", "default_cool"],
                    "options": {
                        "temp_unit": ["fahrenheit", "celsius"],
                        "default_heat": list(range(60, 76)),
                        "default_cool": list(range(68, 80))
                    }
                }
            ))
        elif device.category == DeviceCategory.SECURITY:
            steps.extend([
                PairingStep(
                    id="security_config",
                    title="Security Settings",
                    description="Configure security and access settings",
                    type="input",
                    data={
                        "fields": ["require_pin", "notify_on_trigger", "arm_delay"],
                        "options": {
                            "arm_delay": [0, 30, 60, 120]
                        }
                    }
                ),
                PairingStep(
                    id="security_pin",
                    title="Set Access PIN",
                    description="Create a PIN code for this device",
                    type="input",
                    data={"fields": ["pin"], "format": "4-6 digits"}
                )
            ])
        elif device.category == DeviceCategory.LOCK:
            steps.extend([
                PairingStep(
                    id="lock_admin",
                    title="Admin Setup",
                    description="Set up administrator access for the lock",
                    type="input",
                    data={"fields": ["admin_code", "auto_lock", "auto_lock_delay"]}
                ),
                PairingStep(
                    id="lock_test",
                    title="Test Lock",
                    description="Test the lock/unlock functionality",
                    type="action",
                    data={"actions": ["lock", "unlock", "lock"]}
                )
            ])
        
        # Common final steps
        steps.extend([
            PairingStep(
                id="name_device",
                title="Name Your Device",
                description="Give your device a friendly name",
                type="input",
                data={"fields": ["friendly_name", "room"]}
            ),
            PairingStep(
                id="test_connection",
                title="Test Connection",
                description="Testing communication with your device...",
                type="test"
            ),
            PairingStep(
                id="complete",
                title="Setup Complete!",
                description="Your device is now paired and ready to use",
                type="info"
            )
        ])
        
        return steps


class IoTPairingWizard:
    """Manages IoT device pairing sessions"""
    
    def __init__(self, discovery_module=None):
        self.discovery = discovery_module
        self.sessions: Dict[str, PairingSession] = {}
        self.paired_devices: Dict[str, Dict[str, Any]] = {}
        
    def create_session(
        self,
        device: DiscoveredDevice,
        user_id: str
    ) -> PairingSession:
        """Create a new pairing session"""
        session_id = f"pair_{secrets.token_hex(8)}"
        
        steps = PairingWizardTemplates.get_steps_for_device(device)
        
        session = PairingSession(
            id=session_id,
            device=device,
            user_id=user_id,
            created_at=datetime.now(),
            steps=steps
        )
        
        self.sessions[session_id] = session
        logger.info(f"Created pairing session {session_id} for {device.name}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[PairingSession]:
        """Get a pairing session by ID"""
        return self.sessions.get(session_id)
    
    def get_current_step(self, session_id: str) -> Optional[PairingStep]:
        """Get the current step for a session"""
        session = self.sessions.get(session_id)
        if not session or session.current_step >= len(session.steps):
            return None
        return session.steps[session.current_step]
    
    async def advance_step(
        self,
        session_id: str,
        user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Advance to the next step in the wizard"""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        current_step = session.steps[session.current_step]
        
        # Store user input
        if user_input:
            current_step.user_input = user_input
        
        # Validate if required
        if current_step.validation:
            if not current_step.validation(user_input):
                return {"success": False, "error": "Validation failed"}
        
        # Execute step-specific actions
        result = await self._execute_step(session, current_step)
        if not result["success"]:
            return result
        
        # Mark step as completed
        current_step.completed = True
        
        # Move to next step
        session.current_step += 1
        
        # Check if completed
        if session.current_step >= len(session.steps):
            session.status = PairingStatus.COMPLETED
            await self._finalize_pairing(session)
            return {
                "success": True,
                "completed": True,
                "message": "Device paired successfully!",
                "device_id": session.device.id
            }
        
        # Return next step
        next_step = session.steps[session.current_step]
        return {
            "success": True,
            "completed": False,
            "next_step": {
                "id": next_step.id,
                "title": next_step.title,
                "description": next_step.description,
                "type": next_step.type,
                "data": next_step.data
            }
        }
    
    async def _execute_step(
        self,
        session: PairingSession,
        step: PairingStep
    ) -> Dict[str, Any]:
        """Execute step-specific actions"""
        
        if step.type == "info" or step.type == "confirm":
            return {"success": True}
        
        if step.id == "wifi_credentials":
            # Would actually configure device WiFi
            session.status = PairingStatus.CONFIGURING
            await asyncio.sleep(0.5)  # Simulate configuration
            return {"success": True}
        
        if step.id == "zigbee_pairing":
            session.status = PairingStatus.CONFIGURING
            # Would actually trigger Zigbee pairing
            await asyncio.sleep(0.5)
            return {"success": True}
        
        if step.id == "matter_commission":
            session.status = PairingStatus.CONFIGURING
            # Would actually commission Matter device
            await asyncio.sleep(1)
            return {"success": True}
        
        if step.id == "test_connection":
            session.status = PairingStatus.TESTING
            # Would actually test the device
            await asyncio.sleep(0.5)
            return {"success": True}
        
        return {"success": True}
    
    async def _finalize_pairing(self, session: PairingSession):
        """Finalize device pairing and store configuration"""
        # Collect all user inputs from steps
        config = {}
        for step in session.steps:
            if step.user_input:
                config.update(step.user_input)
        
        # Store paired device
        device_record = {
            "device": session.device.to_dict(),
            "config": config,
            "paired_at": datetime.now().isoformat(),
            "paired_by": session.user_id
        }
        
        self.paired_devices[session.device.id] = device_record
        logger.info(f"Device {session.device.id} paired successfully")
    
    def cancel_session(self, session_id: str) -> bool:
        """Cancel a pairing session"""
        if session_id in self.sessions:
            self.sessions[session_id].status = PairingStatus.FAILED
            self.sessions[session_id].error_message = "Cancelled by user"
            del self.sessions[session_id]
            return True
        return False
    
    def get_paired_devices(self) -> List[Dict[str, Any]]:
        """Get all paired devices"""
        return list(self.paired_devices.values())
    
    def unpair_device(self, device_id: str) -> bool:
        """Unpair a device"""
        if device_id in self.paired_devices:
            del self.paired_devices[device_id]
            logger.info(f"Device {device_id} unpaired")
            return True
        return False


# FastAPI routes
def create_pairing_routes():
    """Create FastAPI routes for device pairing"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/api/pairing", tags=["pairing"])
    wizard = IoTPairingWizard()
    
    # Sample discovered devices for demo
    DEMO_DEVICES = [
        DiscoveredDevice(
            id="demo_light_1",
            name="Living Room Light",
            manufacturer="Philips",
            model="Hue Bulb A19",
            category=DeviceCategory.LIGHTING,
            connection_type=ConnectionType.ZIGBEE,
            capabilities=["on_off", "brightness", "color", "color_temp"]
        ),
        DiscoveredDevice(
            id="demo_thermostat_1",
            name="Smart Thermostat",
            manufacturer="Ecobee",
            model="SmartThermostat",
            category=DeviceCategory.CLIMATE,
            connection_type=ConnectionType.WIFI,
            ip_address="192.168.1.100",
            capabilities=["heat", "cool", "fan", "schedule"]
        ),
        DiscoveredDevice(
            id="demo_lock_1",
            name="Front Door Lock",
            manufacturer="August",
            model="Smart Lock Pro",
            category=DeviceCategory.LOCK,
            connection_type=ConnectionType.BLUETOOTH,
            capabilities=["lock", "unlock", "auto_lock", "access_codes"]
        )
    ]
    
    class StartPairingRequest(BaseModel):
        device_id: str
        user_id: str
    
    class AdvanceStepRequest(BaseModel):
        user_input: Optional[Dict[str, Any]] = None
    
    @router.get("/discover")
    async def discover_devices():
        """Get list of discoverable devices"""
        return {"devices": [d.to_dict() for d in DEMO_DEVICES]}
    
    @router.post("/start")
    async def start_pairing(request: StartPairingRequest):
        """Start a new pairing session"""
        device = next((d for d in DEMO_DEVICES if d.id == request.device_id), None)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        session = wizard.create_session(device, request.user_id)
        first_step = session.steps[0] if session.steps else None
        
        return {
            "session_id": session.id,
            "device": device.to_dict(),
            "total_steps": len(session.steps),
            "current_step": {
                "id": first_step.id,
                "title": first_step.title,
                "description": first_step.description,
                "type": first_step.type,
                "data": first_step.data
            } if first_step else None
        }
    
    @router.post("/session/{session_id}/advance")
    async def advance_pairing(session_id: str, request: AdvanceStepRequest):
        """Advance to the next step in pairing"""
        result = await wizard.advance_step(session_id, request.user_input)
        if not result["success"] and "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @router.get("/session/{session_id}")
    async def get_session_status(session_id: str):
        """Get current session status"""
        session = wizard.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_dict()
    
    @router.delete("/session/{session_id}")
    async def cancel_pairing(session_id: str):
        """Cancel a pairing session"""
        if wizard.cancel_session(session_id):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Session not found")
    
    @router.get("/devices")
    async def get_paired_devices():
        """Get all paired devices"""
        return {"devices": wizard.get_paired_devices()}
    
    @router.delete("/devices/{device_id}")
    async def unpair_device(device_id: str):
        """Unpair a device"""
        if wizard.unpair_device(device_id):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Device not found")
    
    return router
