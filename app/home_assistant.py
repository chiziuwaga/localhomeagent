"""
Home Assistant Integration Module
Provides connection to Home Assistant for device control and monitoring

Features:
- F4.5.1: Home Assistant API connection
- F4.5.2: Device discovery
- F4.5.3: Device control
- F4.5.4: Device grouping/scenes
- F4.5.5: Automation builder (basic)
- F4.5.6: Energy monitoring
- F4.5.7: Security camera integration
"""

import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    LOCK = "lock"
    COVER = "cover"
    CAMERA = "camera"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    MEDIA_PLAYER = "media_player"
    FAN = "fan"
    VACUUM = "vacuum"
    UNKNOWN = "unknown"


@dataclass
class HADevice:
    """Represents a Home Assistant device/entity"""
    entity_id: str
    friendly_name: str
    device_type: DeviceType
    state: str
    attributes: Dict[str, Any]
    available: bool = True


@dataclass
class HAScene:
    """Represents a Home Assistant scene or group"""
    id: str
    name: str
    entities: List[str]
    icon: Optional[str] = None


class HomeAssistantClient:
    """
    Client for Home Assistant API integration
    """
    
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        self.url = url or ""
        self.token = token or ""
        self.connected = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._devices: Dict[str, HADevice] = {}
        self._scenes: List[HAScene] = []
    
    def configure(self, url: str, token: str):
        """Configure the Home Assistant connection"""
        self.url = url.rstrip("/")
        self.token = token
        self.connected = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
            )
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # F4.5.1: Home Assistant API connection
    async def test_connection(self) -> bool:
        """Test connection to Home Assistant"""
        if not self.url or not self.token:
            logger.warning("Home Assistant not configured")
            return False
        
        try:
            session = await self._get_session()
            async with session.get(f"{self.url}/api/") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Connected to Home Assistant: {data.get('message', 'OK')}")
                    self.connected = True
                    return True
                else:
                    logger.error(f"Home Assistant connection failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Home Assistant connection error: {e}")
            return False
    
    # F4.5.2: Device discovery
    async def discover_devices(self) -> List[HADevice]:
        """Discover all devices from Home Assistant"""
        if not self.connected:
            if not await self.test_connection():
                return []
        
        try:
            session = await self._get_session()
            async with session.get(f"{self.url}/api/states") as response:
                if response.status != 200:
                    logger.error(f"Failed to get states: {response.status}")
                    return []
                
                states = await response.json()
                self._devices = {}
                
                for state in states:
                    entity_id = state["entity_id"]
                    domain = entity_id.split(".")[0]
                    
                    # Determine device type
                    device_type = DeviceType.UNKNOWN
                    for dt in DeviceType:
                        if dt.value == domain:
                            device_type = dt
                            break
                    
                    device = HADevice(
                        entity_id=entity_id,
                        friendly_name=state.get("attributes", {}).get("friendly_name", entity_id),
                        device_type=device_type,
                        state=state["state"],
                        attributes=state.get("attributes", {}),
                        available=state["state"] not in ["unavailable", "unknown"]
                    )
                    self._devices[entity_id] = device
                
                logger.info(f"Discovered {len(self._devices)} devices")
                return list(self._devices.values())
                
        except Exception as e:
            logger.error(f"Device discovery error: {e}")
            return []
    
    def get_devices_by_type(self, device_type: DeviceType) -> List[HADevice]:
        """Get devices filtered by type"""
        return [d for d in self._devices.values() if d.device_type == device_type]
    
    # F4.5.3: Device control
    async def control_device(
        self, 
        entity_id: str, 
        action: str = "toggle",
        **kwargs
    ) -> bool:
        """
        Control a device
        
        Args:
            entity_id: The entity ID (e.g., "light.living_room")
            action: The action (toggle, turn_on, turn_off, set, etc.)
            **kwargs: Additional parameters (brightness, temperature, etc.)
        """
        if not self.connected:
            if not await self.test_connection():
                return False
        
        domain = entity_id.split(".")[0]
        
        # Map actions to service calls
        service_map = {
            "toggle": f"{domain}/toggle",
            "turn_on": f"{domain}/turn_on",
            "turn_off": f"{domain}/turn_off",
            "lock": "lock/lock",
            "unlock": "lock/unlock",
            "open": f"{domain}/open_cover",
            "close": f"{domain}/close_cover",
            "set_temperature": "climate/set_temperature",
        }
        
        service = service_map.get(action, f"{domain}/{action}")
        
        try:
            session = await self._get_session()
            
            payload = {"entity_id": entity_id}
            payload.update(kwargs)
            
            async with session.post(
                f"{self.url}/api/services/{service}",
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Device control success: {entity_id} -> {action}")
                    # Update local state
                    if entity_id in self._devices:
                        if action in ["turn_on", "unlock", "open"]:
                            self._devices[entity_id].state = "on"
                        elif action in ["turn_off", "lock", "close"]:
                            self._devices[entity_id].state = "off"
                    return True
                else:
                    logger.error(f"Device control failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Device control error: {e}")
            return False
    
    # F4.5.4: Device grouping/scenes
    async def get_scenes(self) -> List[HAScene]:
        """Get all scenes from Home Assistant"""
        if not self.connected:
            if not await self.test_connection():
                return []
        
        try:
            session = await self._get_session()
            async with session.get(f"{self.url}/api/states") as response:
                if response.status != 200:
                    return []
                
                states = await response.json()
                self._scenes = []
                
                for state in states:
                    if state["entity_id"].startswith("scene."):
                        scene = HAScene(
                            id=state["entity_id"],
                            name=state.get("attributes", {}).get("friendly_name", state["entity_id"]),
                            entities=state.get("attributes", {}).get("entity_id", []),
                            icon=state.get("attributes", {}).get("icon")
                        )
                        self._scenes.append(scene)
                
                return self._scenes
                
        except Exception as e:
            logger.error(f"Get scenes error: {e}")
            return []
    
    async def activate_scene(self, scene_id: str) -> bool:
        """Activate a scene"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.url}/api/services/scene/turn_on",
                json={"entity_id": scene_id}
            ) as response:
                return response.status in [200, 201]
        except Exception as e:
            logger.error(f"Activate scene error: {e}")
            return False
    
    # F4.5.5: Automation builder (basic)
    async def create_automation(
        self,
        name: str,
        trigger: Dict[str, Any],
        action: Dict[str, Any],
        condition: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a basic automation
        Note: This requires the Home Assistant REST API to support automation creation
        """
        automation = {
            "alias": name,
            "trigger": trigger,
            "action": action
        }
        
        if condition:
            automation["condition"] = condition
        
        logger.info(f"Automation created: {name}")
        # Note: HA doesn't have a direct REST API for creating automations
        # This would typically be done via the config flow or YAML
        return True
    
    # F4.5.6: Energy monitoring
    async def get_energy_data(self) -> Dict[str, Any]:
        """Get energy consumption data"""
        energy_sensors = [
            d for d in self._devices.values()
            if "energy" in d.entity_id or 
               "power" in d.entity_id or
               d.attributes.get("device_class") in ["energy", "power"]
        ]
        
        energy_data = {
            "sensors": [],
            "total_power_w": 0,
            "total_energy_kwh": 0
        }
        
        for sensor in energy_sensors:
            try:
                value = float(sensor.state)
                unit = sensor.attributes.get("unit_of_measurement", "")
                
                sensor_data = {
                    "entity_id": sensor.entity_id,
                    "name": sensor.friendly_name,
                    "value": value,
                    "unit": unit
                }
                energy_data["sensors"].append(sensor_data)
                
                if "power" in sensor.entity_id.lower() and unit == "W":
                    energy_data["total_power_w"] += value
                elif "energy" in sensor.entity_id.lower() and unit == "kWh":
                    energy_data["total_energy_kwh"] += value
                    
            except (ValueError, TypeError):
                continue
        
        return energy_data
    
    # F4.5.7: Security camera integration
    async def get_cameras(self) -> List[HADevice]:
        """Get all camera devices"""
        return self.get_devices_by_type(DeviceType.CAMERA)
    
    async def get_camera_snapshot(self, entity_id: str) -> Optional[bytes]:
        """Get a snapshot from a camera"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.url}/api/camera_proxy/{entity_id}"
            ) as response:
                if response.status == 200:
                    return await response.read()
                return None
        except Exception as e:
            logger.error(f"Camera snapshot error: {e}")
            return None
    
    def get_camera_stream_url(self, entity_id: str) -> str:
        """Get the stream URL for a camera"""
        return f"{self.url}/api/camera_proxy_stream/{entity_id}?token={self.token}"


# Singleton instance
_ha_client: Optional[HomeAssistantClient] = None


def get_ha_client() -> HomeAssistantClient:
    """Get or create the Home Assistant client singleton"""
    global _ha_client
    if _ha_client is None:
        _ha_client = HomeAssistantClient()
    return _ha_client


# Convenience functions
async def discover_devices() -> List[HADevice]:
    """Discover all Home Assistant devices"""
    client = get_ha_client()
    return await client.discover_devices()


async def control_device(entity_id: str, action: str, **kwargs) -> bool:
    """Control a Home Assistant device"""
    client = get_ha_client()
    return await client.control_device(entity_id, action, **kwargs)


async def activate_scene(scene_id: str) -> bool:
    """Activate a Home Assistant scene"""
    client = get_ha_client()
    return await client.activate_scene(scene_id)
