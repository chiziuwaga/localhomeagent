"""
IoT Device Discovery Module
Provides comprehensive network scanning and device discovery for IoT devices

Protocols supported DIRECTLY:
- mDNS/Bonjour (HomeKit, Chromecast, AirPlay, Spotify Connect)
- SSDP/UPnP (Roku, Samsung/LG TVs, Sonos, WeMo)
- ARP scanning (MAC-based manufacturer identification)
- MQTT discovery (IoT sensors, ESP devices)
- BLE scanning (Bluetooth Low Energy devices)
- Matter/Thread (via mDNS _matter._tcp, _matterc._udp)

Protocols supported via HOME ASSISTANT:
- Zigbee (requires Zigbee coordinator: ZHA, Zigbee2MQTT)
- Z-Wave (requires Z-Wave controller)
- Thread border router
- Matter (full commissioning)

Security Rationale:
- All discovery is passive (listening) or uses standard broadcast protocols
- No port scanning or intrusive probing
- Discovered devices are only controlled via Home Assistant for security
- MAC addresses help identify trusted vs unknown devices
"""

import asyncio
import socket
import logging
import struct
import json
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import subprocess
import time

logger = logging.getLogger(__name__)


class DiscoveryProtocol(Enum):
    MDNS = "mDNS"
    SSDP = "SSDP"
    ARP = "ARP"
    MQTT = "MQTT"
    BLE = "BLE"
    MATTER = "Matter"
    THREAD = "Thread"
    HOME_ASSISTANT = "HomeAssistant"
    MANUAL = "Manual"


class DeviceCategory(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    OUTLET = "outlet"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    DOORBELL = "doorbell"
    SPEAKER = "speaker"
    TV = "tv"
    HUB = "hub"
    BRIDGE = "bridge"
    SENSOR = "sensor"
    MOTION = "motion"
    DOOR_WINDOW = "door_window"
    CLIMATE = "climate"
    FAN = "fan"
    BLIND = "blind"
    GARAGE = "garage"
    VACUUM = "vacuum"
    APPLIANCE = "appliance"
    UNKNOWN = "unknown"


class SecurityTrust(Enum):
    """Security trust level for discovered devices"""
    TRUSTED = "trusted"      # Known device, verified
    KNOWN = "known"          # Recognized manufacturer
    UNKNOWN = "unknown"      # Unknown device, needs review
    SUSPICIOUS = "suspicious" # Unusual behavior or signature


@dataclass
class DiscoveredDevice:
    """Represents a discovered IoT device on the network"""
    ip: str
    mac: Optional[str]
    name: str
    manufacturer: Optional[str]
    model: Optional[str]
    category: DeviceCategory
    protocol: DiscoveryProtocol
    port: int = 80
    services: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trust_level: SecurityTrust = SecurityTrust.UNKNOWN
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    firmware_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "ip": self.ip,
            "mac": self.mac,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "category": self.category.value,
            "protocol": self.protocol.value,
            "port": self.port,
            "services": self.services,
            "metadata": self.metadata,
            "trust_level": self.trust_level.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
            "firmware_version": self.firmware_version,
        }


# Comprehensive device signatures database
DEVICE_SIGNATURES = {
    # MAC address prefixes (OUI - Organizationally Unique Identifier)
    "mac_prefixes": {
        # Raspberry Pi / DIY
        "B8:27:EB": ("Raspberry Pi", DeviceCategory.HUB),
        "DC:A6:32": ("Raspberry Pi", DeviceCategory.HUB),
        "E4:5F:01": ("Raspberry Pi", DeviceCategory.HUB),
        
        # Philips / Signify (Hue)
        "00:17:88": ("Philips Hue", DeviceCategory.LIGHT),
        "EC:B5:FA": ("Philips Hue", DeviceCategory.LIGHT),
        
        # LIFX
        "D0:73:D5": ("LIFX", DeviceCategory.LIGHT),
        
        # Ring (Amazon)
        "68:A4:0E": ("Ring", DeviceCategory.DOORBELL),
        "5C:47:5E": ("Ring", DeviceCategory.CAMERA),
        
        # Amazon Echo/Alexa
        "FC:A1:83": ("Amazon Echo", DeviceCategory.SPEAKER),
        "44:00:49": ("Amazon Echo", DeviceCategory.SPEAKER),
        "A4:08:01": ("Amazon Echo", DeviceCategory.SPEAKER),
        "74:C2:46": ("Amazon Echo", DeviceCategory.SPEAKER),
        
        # Google/Nest
        "18:B4:30": ("Nest", DeviceCategory.THERMOSTAT),
        "64:16:66": ("Nest", DeviceCategory.THERMOSTAT),
        "D4:F5:47": ("Google Home", DeviceCategory.SPEAKER),
        "30:FD:38": ("Google Home", DeviceCategory.SPEAKER),
        "F4:F5:D8": ("Google Nest", DeviceCategory.HUB),
        "1C:F2:9A": ("Google Chromecast", DeviceCategory.TV),
        
        # Apple
        "F0:D1:A9": ("Apple HomePod", DeviceCategory.SPEAKER),
        "70:3E:AC": ("Apple TV", DeviceCategory.TV),
        
        # Samsung
        "AC:5A:F0": ("Samsung SmartThings", DeviceCategory.HUB),
        "BC:8C:CD": ("Samsung TV", DeviceCategory.TV),
        "78:AB:BB": ("Samsung TV", DeviceCategory.TV),
        
        # LG
        "00:1A:22": ("LG TV", DeviceCategory.TV),
        "64:99:5D": ("LG TV", DeviceCategory.TV),
        
        # TP-Link / Kasa / Tapo
        "84:D4:7E": ("TP-Link Kasa", DeviceCategory.SWITCH),
        "50:C7:BF": ("TP-Link Kasa", DeviceCategory.SWITCH),
        "98:DA:C4": ("TP-Link Tapo", DeviceCategory.CAMERA),
        "B4:B0:24": ("TP-Link Tapo", DeviceCategory.SWITCH),
        
        # Wyze
        "B0:BE:83": ("Wyze", DeviceCategory.CAMERA),
        "2C:AA:8E": ("Wyze", DeviceCategory.CAMERA),
        "D0:3F:27": ("Wyze", DeviceCategory.SWITCH),
        
        # ecobee
        "7C:49:EB": ("ecobee", DeviceCategory.THERMOSTAT),
        "44:61:32": ("ecobee", DeviceCategory.THERMOSTAT),
        
        # Sonos
        "94:9F:3E": ("Sonos", DeviceCategory.SPEAKER),
        "78:28:CA": ("Sonos", DeviceCategory.SPEAKER),
        "B8:E9:37": ("Sonos", DeviceCategory.SPEAKER),
        
        # Roku
        "B0:A7:37": ("Roku", DeviceCategory.TV),
        "C8:3A:6B": ("Roku", DeviceCategory.TV),
        "D4:3A:2E": ("Roku", DeviceCategory.TV),
        
        # Wemo (Belkin)
        "94:10:3E": ("Wemo", DeviceCategory.SWITCH),
        "EC:1A:59": ("Wemo", DeviceCategory.SWITCH),
        
        # Tuya / Smart Life (many white-label devices)
        "D8:F1:5B": ("Tuya", DeviceCategory.SWITCH),
        "10:D5:61": ("Tuya", DeviceCategory.SWITCH),
        "A4:CF:12": ("Tuya", DeviceCategory.LIGHT),
        
        # Shelly
        "E8:68:E7": ("Shelly", DeviceCategory.SWITCH),
        "C4:5B:BE": ("Shelly", DeviceCategory.SWITCH),
        
        # Govee
        "E0:00:84": ("Govee", DeviceCategory.LIGHT),
        
        # Yale / August (locks)
        "00:1E:C0": ("Yale", DeviceCategory.LOCK),
        "D0:03:4B": ("August", DeviceCategory.LOCK),
        
        # Schlage
        "00:24:46": ("Schlage", DeviceCategory.LOCK),
        
        # Arlo
        "28:B4:48": ("Arlo", DeviceCategory.CAMERA),
        "44:6F:D8": ("Arlo", DeviceCategory.CAMERA),
        
        # Eufy
        "E4:AA:EC": ("Eufy", DeviceCategory.CAMERA),
        "F8:CA:B8": ("Eufy", DeviceCategory.VACUUM),
        
        # iRobot Roomba
        "50:14:79": ("iRobot Roomba", DeviceCategory.VACUUM),
        "80:C5:F2": ("iRobot Roomba", DeviceCategory.VACUUM),
        
        # Zigbee/Z-Wave Coordinators
        "00:0D:6F": ("Zigbee Coordinator", DeviceCategory.HUB),
        "00:12:4B": ("TI Zigbee", DeviceCategory.HUB),
        "00:15:8D": ("Aeotec Z-Wave", DeviceCategory.HUB),
        
        # Matter/Thread
        "E0:03:9F": ("Thread Border Router", DeviceCategory.HUB),
        
        # ESP/Arduino (DIY devices)
        "24:0A:C4": ("Espressif ESP32", DeviceCategory.SENSOR),
        "30:AE:A4": ("Espressif ESP8266", DeviceCategory.SENSOR),
        "A4:CF:12": ("Espressif", DeviceCategory.SENSOR),
        "C4:4F:33": ("Espressif", DeviceCategory.SENSOR),
    },
    
    # mDNS service types (expanded)
    "mdns_services": {
        # HomeKit
        "_hap._tcp": ("HomeKit Accessory", DeviceCategory.UNKNOWN),
        "_homekit._tcp": ("HomeKit", DeviceCategory.UNKNOWN),
        
        # Casting
        "_googlecast._tcp": ("Google Cast", DeviceCategory.SPEAKER),
        "_spotify-connect._tcp": ("Spotify Connect", DeviceCategory.SPEAKER),
        "_airplay._tcp": ("AirPlay", DeviceCategory.SPEAKER),
        "_raop._tcp": ("AirPlay Audio", DeviceCategory.SPEAKER),
        
        # Specific devices
        "_hue._tcp": ("Philips Hue", DeviceCategory.LIGHT),
        "_sonos._tcp": ("Sonos", DeviceCategory.SPEAKER),
        "_nanoleaf._tcp": ("Nanoleaf", DeviceCategory.LIGHT),
        "_elg._tcp": ("Elgato", DeviceCategory.LIGHT),
        
        # Matter/Thread
        "_matter._tcp": ("Matter Device", DeviceCategory.UNKNOWN),
        "_matterc._udp": ("Matter Commissioner", DeviceCategory.HUB),
        "_meshcop._udp": ("Thread Mesh CoP", DeviceCategory.HUB),
        "_srp._tcp": ("Thread SRP", DeviceCategory.HUB),
        
        # Home automation hubs
        "_mqtt._tcp": ("MQTT Broker", DeviceCategory.HUB),
        "_home-assistant._tcp": ("Home Assistant", DeviceCategory.HUB),
        "_esphomelib._tcp": ("ESPHome", DeviceCategory.SENSOR),
        "_hass._tcp": ("Home Assistant", DeviceCategory.HUB),
        
        # Other services
        "_http._tcp": ("HTTP Device", DeviceCategory.UNKNOWN),
        "_https._tcp": ("HTTPS Device", DeviceCategory.UNKNOWN),
        "_ssh._tcp": ("SSH Server", DeviceCategory.HUB),
        "_printer._tcp": ("Printer", DeviceCategory.APPLIANCE),
        "_ipp._tcp": ("IPP Printer", DeviceCategory.APPLIANCE),
        "_daap._tcp": ("iTunes/DAAP", DeviceCategory.SPEAKER),
        "_smb._tcp": ("Samba/SMB", DeviceCategory.HUB),
    },
    
    # SSDP/UPnP device types (expanded)
    "ssdp_types": {
        "urn:schemas-upnp-org:device:MediaRenderer:1": DeviceCategory.SPEAKER,
        "urn:schemas-upnp-org:device:MediaServer:1": DeviceCategory.HUB,
        "urn:dial-multiscreen-org:service:dial:1": DeviceCategory.TV,
        "urn:Belkin:device:controllee:1": DeviceCategory.SWITCH,
        "urn:Belkin:device:insight:1": DeviceCategory.SWITCH,
        "urn:Belkin:device:sensor:1": DeviceCategory.SENSOR,
        "urn:Belkin:device:bridge:1": DeviceCategory.BRIDGE,
        "urn:roku-com:device:player:1-0": DeviceCategory.TV,
        "urn:samsung.com:device:RemoteControlReceiver:1": DeviceCategory.TV,
        "urn:LGE-com:service:webos-second-screen:1": DeviceCategory.TV,
        "urn:schemas-upnp-org:device:InternetGatewayDevice:1": DeviceCategory.HUB,
        "urn:schemas-upnp-org:device:ZonePlayer:1": DeviceCategory.SPEAKER,
    },
    
    # MQTT topic patterns for auto-discovery
    "mqtt_topics": {
        "homeassistant/": "Home Assistant MQTT Discovery",
        "tasmota/": "Tasmota Device",
        "zigbee2mqtt/": "Zigbee2MQTT",
        "esphome/": "ESPHome Device",
        "shellies/": "Shelly Device",
        "tuya/": "Tuya Device",
    }
}
        "_spotify-connect._tcp": ("Spotify Connect", DeviceCategory.SPEAKER),
        "_airplay._tcp": ("AirPlay", DeviceCategory.SPEAKER),
        "_raop._tcp": ("AirPlay Audio", DeviceCategory.SPEAKER),
        "_hue._tcp": ("Philips Hue", DeviceCategory.LIGHT),
        "_mqtt._tcp": ("MQTT Broker", DeviceCategory.HUB),
        "_home-assistant._tcp": ("Home Assistant", DeviceCategory.HUB),
    },
    
    # SSDP/UPnP device types
    "ssdp_types": {
        "urn:schemas-upnp-org:device:MediaRenderer": DeviceCategory.SPEAKER,
        "urn:schemas-upnp-org:device:MediaServer": DeviceCategory.HUB,
        "urn:dial-multiscreen-org:service:dial:1": DeviceCategory.TV,
        "urn:Belkin:device:controllee": DeviceCategory.SWITCH,
        "urn:Belkin:device:insight": DeviceCategory.SWITCH,
    }
}


class IoTDiscovery:
    """
    IoT Device Discovery Manager
    
    Scans the local network for IoT devices using multiple protocols.
    Most actual device control is delegated to Home Assistant.
    """
    
    def __init__(self):
        self.discovered_devices: Dict[str, DiscoveredDevice] = {}
        self.scan_in_progress = False
        
    async def scan_network(self, timeout: float = 10.0) -> List[DiscoveredDevice]:
        """
        Perform a full network scan using all available protocols
        """
        if self.scan_in_progress:
            logger.warning("Scan already in progress")
            return list(self.discovered_devices.values())
        
        self.scan_in_progress = True
        logger.info("Starting comprehensive IoT device discovery scan...")
        
        try:
            # Run all scans in parallel for speed
            results = await asyncio.gather(
                self._scan_mdns(timeout),
                self._scan_ssdp(timeout),
                self._scan_arp(),
                self._scan_matter_thread(timeout),
                self._scan_mqtt_devices(),
                self._scan_ble_devices(timeout),
                return_exceptions=True
            )
            
            # Merge results
            for result in results:
                if isinstance(result, list):
                    for device in result:
                        key = device.ip or device.mac or device.name
                        if key:
                            # Merge with existing device info
                            if key in self.discovered_devices:
                                self._merge_device(self.discovered_devices[key], device)
                            else:
                                self.discovered_devices[key] = device
                                # Assign trust level based on manufacturer
                                self._assign_trust_level(self.discovered_devices[key])
                elif isinstance(result, Exception):
                    logger.error(f"Scan error: {result}")
            
            logger.info(f"Discovery complete. Found {len(self.discovered_devices)} devices")
            return list(self.discovered_devices.values())
            
        finally:
            self.scan_in_progress = False
    
    def _assign_trust_level(self, device: DiscoveredDevice):
        """Assign security trust level based on device characteristics"""
        if device.manufacturer:
            # Known manufacturers are at least "known"
            device.trust_level = SecurityTrust.KNOWN
            
            # Well-known trusted brands
            trusted_brands = [
                "Philips Hue", "Nest", "Google", "Apple", "Amazon Echo",
                "Sonos", "ecobee", "Ring", "Yale", "Schlage", "Home Assistant"
            ]
            if any(brand in device.manufacturer for brand in trusted_brands):
                device.trust_level = SecurityTrust.TRUSTED
        else:
            # Unknown manufacturer
            device.trust_level = SecurityTrust.UNKNOWN
            
            # Check for suspicious characteristics
            if device.protocol == DiscoveryProtocol.ARP and not device.services:
                # Device discovered only via ARP with no services
                device.trust_level = SecurityTrust.SUSPICIOUS
    
    async def _scan_mdns(self, timeout: float) -> List[DiscoveredDevice]:
        """
        Scan for devices using mDNS/Bonjour
        This finds HomeKit, Chromecast, AirPlay devices, etc.
        """
        devices = []
        
        try:
            # Try to use zeroconf if available
            try:
                from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
                
                class Listener(ServiceListener):
                    def __init__(self):
                        self.found = []
                    
                    def add_service(self, zc, type_, name):
                        info = zc.get_service_info(type_, name)
                        if info:
                            self.found.append({
                                "name": name,
                                "type": type_,
                                "address": socket.inet_ntoa(info.addresses[0]) if info.addresses else None,
                                "port": info.port,
                                "properties": dict(info.properties) if info.properties else {}
                            })
                    
                    def remove_service(self, zc, type_, name):
                        pass
                    
                    def update_service(self, zc, type_, name):
                        pass
                
                zc = Zeroconf()
                listener = Listener()
                
                # Browse common IoT service types
                service_types = list(DEVICE_SIGNATURES["mdns_services"].keys())
                browsers = [
                    ServiceBrowser(zc, st + ".local.", listener) 
                    for st in service_types
                ]
                
                await asyncio.sleep(timeout)
                
                for item in listener.found:
                    manufacturer, category = DEVICE_SIGNATURES["mdns_services"].get(
                        item["type"].rstrip(".local."), 
                        ("Unknown", DeviceCategory.UNKNOWN)
                    )
                    
                    device = DiscoveredDevice(
                        ip=item["address"],
                        mac=None,
                        name=item["name"].split(".")[0],
                        manufacturer=manufacturer,
                        model=None,
                        category=category,
                        protocol=DiscoveryProtocol.MDNS,
                        port=item["port"],
                        services=[item["type"]],
                        metadata=item["properties"]
                    )
                    devices.append(device)
                
                zc.close()
                
            except ImportError:
                logger.debug("zeroconf not installed, skipping mDNS scan")
                
        except Exception as e:
            logger.error(f"mDNS scan error: {e}")
        
        return devices
    
    async def _scan_ssdp(self, timeout: float) -> List[DiscoveredDevice]:
        """
        Scan for devices using SSDP (Simple Service Discovery Protocol)
        This finds UPnP devices, Roku, some TVs, etc.
        """
        devices = []
        
        try:
            SSDP_ADDR = "239.255.255.250"
            SSDP_PORT = 1900
            
            # SSDP M-SEARCH message
            message = (
                "M-SEARCH * HTTP/1.1\r\n"
                f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
                'MAN: "ssdp:discover"\r\n'
                "MX: 3\r\n"
                "ST: ssdp:all\r\n"
                "\r\n"
            )
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            
            # Send discovery message
            sock.sendto(message.encode(), (SSDP_ADDR, SSDP_PORT))
            
            # Collect responses
            responses = []
            try:
                while True:
                    data, addr = sock.recvfrom(65507)
                    responses.append((data.decode('utf-8', errors='ignore'), addr))
            except socket.timeout:
                pass
            finally:
                sock.close()
            
            # Parse responses
            for data, (ip, port) in responses:
                device_info = self._parse_ssdp_response(data)
                if device_info:
                    device_type = device_info.get("st", "")
                    category = DeviceCategory.UNKNOWN
                    
                    for pattern, cat in DEVICE_SIGNATURES["ssdp_types"].items():
                        if pattern in device_type:
                            category = cat
                            break
                    
                    device = DiscoveredDevice(
                        ip=ip,
                        mac=None,
                        name=device_info.get("server", "Unknown Device"),
                        manufacturer=None,
                        model=None,
                        category=category,
                        protocol=DiscoveryProtocol.SSDP,
                        services=[device_type],
                        metadata=device_info
                    )
                    devices.append(device)
                    
        except Exception as e:
            logger.error(f"SSDP scan error: {e}")
        
        return devices
    
    def _parse_ssdp_response(self, data: str) -> Optional[Dict[str, str]]:
        """Parse SSDP response headers"""
        result = {}
        for line in data.split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.lower().strip()] = value.strip()
        return result if result else None
    
    async def _scan_arp(self) -> List[DiscoveredDevice]:
        """
        Scan ARP table for device MAC addresses
        This helps identify devices by manufacturer
        """
        devices = []
        
        try:
            import subprocess
            
            # Get ARP table
            if socket.gethostname():
                result = subprocess.run(
                    ["arp", "-a"], 
                    capture_output=True, 
                    text=True,
                    timeout=5
                )
                
                # Parse ARP output (format varies by OS)
                for line in result.stdout.split("\n"):
                    # Try to extract IP and MAC
                    ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                    mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", line)
                    
                    if ip_match and mac_match:
                        ip = ip_match.group(1)
                        mac = mac_match.group(0).upper().replace("-", ":")
                        
                        # Identify by MAC prefix
                        mac_prefix = ":".join(mac.split(":")[:3])
                        manufacturer, category = DEVICE_SIGNATURES["mac_prefixes"].get(
                            mac_prefix, 
                            (None, DeviceCategory.UNKNOWN)
                        )
                        
                        if manufacturer:
                            device = DiscoveredDevice(
                                ip=ip,
                                mac=mac,
                                name=manufacturer,
                                manufacturer=manufacturer,
                                model=None,
                                category=category,
                                protocol=DiscoveryProtocol.ARP
                            )
                            devices.append(device)
                            
        except Exception as e:
            logger.debug(f"ARP scan error: {e}")
        
        return devices
    
    async def _scan_matter_thread(self, timeout: float) -> List[DiscoveredDevice]:
        """
        Scan for Matter and Thread devices via mDNS
        
        Matter devices advertise via:
        - _matter._tcp (commissioned devices)
        - _matterc._udp (commissioning mode)
        
        Thread devices advertise via:
        - _meshcop._udp (Thread Mesh Commissioner)
        - _srp._tcp (Service Registration Protocol)
        """
        devices = []
        
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            
            class MatterListener(ServiceListener):
                def __init__(self):
                    self.found = []
                
                def add_service(self, zc, type_, name):
                    info = zc.get_service_info(type_, name)
                    if info:
                        # Extract Matter-specific info from TXT records
                        props = {k.decode() if isinstance(k, bytes) else k: 
                                v.decode() if isinstance(v, bytes) else v 
                                for k, v in (info.properties or {}).items()}
                        
                        self.found.append({
                            "name": name,
                            "type": type_,
                            "address": socket.inet_ntoa(info.addresses[0]) if info.addresses else None,
                            "port": info.port,
                            "properties": props,
                            "vendor_id": props.get("VP", props.get("VI")),
                            "product_id": props.get("PH", props.get("PI")),
                            "discriminator": props.get("D"),
                        })
                
                def remove_service(self, zc, type_, name):
                    pass
                
                def update_service(self, zc, type_, name):
                    pass
            
            zc = Zeroconf()
            listener = MatterListener()
            
            # Matter and Thread service types
            matter_services = [
                "_matter._tcp.local.",
                "_matterc._udp.local.",
                "_meshcop._udp.local.",
                "_srp._tcp.local.",
                "_thread-bp._udp.local.",
            ]
            
            browsers = [ServiceBrowser(zc, st, listener) for st in matter_services]
            
            await asyncio.sleep(timeout)
            
            for item in listener.found:
                is_thread = "meshcop" in item["type"] or "thread" in item["type"] or "srp" in item["type"]
                
                device = DiscoveredDevice(
                    ip=item["address"],
                    mac=None,
                    name=item["name"].split(".")[0],
                    manufacturer=f"Vendor {item.get('vendor_id', 'Unknown')}",
                    model=f"Product {item.get('product_id', 'Unknown')}",
                    category=DeviceCategory.UNKNOWN,
                    protocol=DiscoveryProtocol.THREAD if is_thread else DiscoveryProtocol.MATTER,
                    port=item["port"],
                    services=[item["type"]],
                    metadata=item["properties"],
                    capabilities=["matter"] if "_matter" in item["type"] else ["thread"],
                )
                devices.append(device)
            
            zc.close()
            
        except ImportError:
            logger.debug("zeroconf not installed, skipping Matter/Thread scan")
        except Exception as e:
            logger.error(f"Matter/Thread scan error: {e}")
        
        return devices
    
    async def _scan_mqtt_devices(self) -> List[DiscoveredDevice]:
        """
        Discover devices via MQTT auto-discovery topics
        
        Supports:
        - Home Assistant MQTT Discovery (homeassistant/)
        - Tasmota devices (tasmota/)
        - Zigbee2MQTT (zigbee2mqtt/)
        - ESPHome (esphome/)
        - Shelly (shellies/)
        """
        devices = []
        
        try:
            import paho.mqtt.client as mqtt
            
            discovered_topics: Set[str] = set()
            
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    # Subscribe to discovery topics
                    for topic_prefix in DEVICE_SIGNATURES["mqtt_topics"].keys():
                        client.subscribe(f"{topic_prefix}#")
            
            def on_message(client, userdata, msg):
                discovered_topics.add(msg.topic)
            
            # Try to connect to local MQTT broker
            mqtt_brokers = [
                ("localhost", 1883),
                ("127.0.0.1", 1883),
                ("mosquitto", 1883),
                ("mqtt", 1883),
            ]
            
            client = mqtt.Client()
            client.on_connect = on_connect
            client.on_message = on_message
            
            connected = False
            for host, port in mqtt_brokers:
                try:
                    client.connect(host, port, 5)
                    connected = True
                    break
                except Exception:
                    continue
            
            if connected:
                client.loop_start()
                await asyncio.sleep(3)  # Wait for messages
                client.loop_stop()
                client.disconnect()
                
                # Parse discovered topics
                for topic in discovered_topics:
                    for prefix, device_type in DEVICE_SIGNATURES["mqtt_topics"].items():
                        if topic.startswith(prefix):
                            # Extract device info from topic
                            parts = topic.replace(prefix, "").split("/")
                            device_name = parts[0] if parts else "MQTT Device"
                            
                            device = DiscoveredDevice(
                                ip="mqtt",  # MQTT devices don't have direct IP
                                mac=None,
                                name=device_name,
                                manufacturer=device_type,
                                model=None,
                                category=DeviceCategory.SENSOR,
                                protocol=DiscoveryProtocol.MQTT,
                                services=[topic],
                                metadata={"topic": topic},
                                capabilities=["mqtt"],
                            )
                            devices.append(device)
                            break
                            
        except ImportError:
            logger.debug("paho-mqtt not installed, skipping MQTT discovery")
        except Exception as e:
            logger.debug(f"MQTT discovery error: {e}")
        
        return devices
    
    async def _scan_ble_devices(self, timeout: float) -> List[DiscoveredDevice]:
        """
        Scan for Bluetooth Low Energy (BLE) devices
        
        Discovers:
        - BLE beacons
        - Smart locks (Yale, August, Schlage)
        - Fitness devices
        - BLE-enabled sensors
        
        Note: Requires bleak library and Bluetooth adapter
        """
        devices = []
        
        try:
            from bleak import BleakScanner
            
            # Known BLE service UUIDs for IoT devices
            KNOWN_BLE_SERVICES = {
                "0000180f-0000-1000-8000-00805f9b34fb": ("Battery Service", DeviceCategory.SENSOR),
                "0000181a-0000-1000-8000-00805f9b34fb": ("Environmental Sensing", DeviceCategory.SENSOR),
                "00001809-0000-1000-8000-00805f9b34fb": ("Health Thermometer", DeviceCategory.SENSOR),
                "0000180d-0000-1000-8000-00805f9b34fb": ("Heart Rate", DeviceCategory.SENSOR),
                "0000fe95-0000-1000-8000-00805f9b34fb": ("Xiaomi Mi", DeviceCategory.SENSOR),
                "0000fef5-0000-1000-8000-00805f9b34fb": ("Dialog Semiconductor", DeviceCategory.SENSOR),
            }
            
            # Manufacturer IDs
            MANUFACTURER_IDS = {
                0x004C: "Apple",
                0x0006: "Microsoft",
                0x00E0: "Google",
                0x0075: "Samsung",
                0x0499: "Ruuvi",
                0x0157: "Xiaomi",
                0x0822: "August",
                0x0969: "Yale",
            }
            
            logger.info("Starting BLE scan...")
            discovered = await BleakScanner.discover(timeout=min(timeout, 5.0))
            
            for d in discovered:
                manufacturer = None
                category = DeviceCategory.UNKNOWN
                
                # Try to identify by manufacturer data
                if d.metadata.get("manufacturer_data"):
                    for mfr_id in d.metadata["manufacturer_data"].keys():
                        if mfr_id in MANUFACTURER_IDS:
                            manufacturer = MANUFACTURER_IDS[mfr_id]
                            break
                
                # Try to identify by service UUIDs
                services = d.metadata.get("uuids", [])
                for uuid in services:
                    uuid_lower = uuid.lower()
                    if uuid_lower in KNOWN_BLE_SERVICES:
                        service_name, cat = KNOWN_BLE_SERVICES[uuid_lower]
                        category = cat
                        break
                
                # Only add if we identified something useful
                if manufacturer or category != DeviceCategory.UNKNOWN or d.name:
                    device = DiscoveredDevice(
                        ip="ble",  # BLE devices don't have IP
                        mac=d.address,
                        name=d.name or f"BLE Device {d.address[-5:]}",
                        manufacturer=manufacturer,
                        model=None,
                        category=category,
                        protocol=DiscoveryProtocol.BLE,
                        services=services,
                        metadata={
                            "rssi": d.rssi,
                            "manufacturer_data": str(d.metadata.get("manufacturer_data", {})),
                        },
                        capabilities=["ble"],
                    )
                    devices.append(device)
            
            logger.info(f"BLE scan found {len(devices)} devices")
            
        except ImportError:
            logger.debug("bleak not installed, skipping BLE scan")
        except Exception as e:
            logger.debug(f"BLE scan error: {e}")
        
        return devices
    
    def _merge_device(self, existing: DiscoveredDevice, new: DiscoveredDevice):
        """Merge information from multiple discovery sources"""
        if new.mac and not existing.mac:
            existing.mac = new.mac
        if new.manufacturer and not existing.manufacturer:
            existing.manufacturer = new.manufacturer
        if new.model and not existing.model:
            existing.model = new.model
        if new.category != DeviceCategory.UNKNOWN and existing.category == DeviceCategory.UNKNOWN:
            existing.category = new.category
        existing.services.extend(new.services)
        existing.metadata.update(new.metadata)
    
    def get_devices_by_category(self, category: DeviceCategory) -> List[DiscoveredDevice]:
        """Filter discovered devices by category"""
        return [d for d in self.discovered_devices.values() if d.category == category]
    
    def get_integrable_devices(self) -> List[Dict[str, Any]]:
        """
        Get devices that can be integrated with Home Assistant
        Returns setup instructions for each device
        """
        integrations = []
        
        for device in self.discovered_devices.values():
            integration = {
                "device": device,
                "integration_method": "home_assistant",
                "setup_steps": []
            }
            
            if "HomeKit" in (device.manufacturer or ""):
                integration["setup_steps"] = [
                    "1. Go to Home Assistant → Settings → Devices & Services",
                    "2. Click 'Add Integration'",
                    "3. Search for 'HomeKit Controller'",
                    "4. Follow the pairing instructions"
                ]
            elif "Philips Hue" in (device.manufacturer or ""):
                integration["setup_steps"] = [
                    "1. Press the button on your Hue bridge",
                    "2. Go to Home Assistant → Settings → Devices & Services",
                    "3. Click 'Add Integration' → 'Philips Hue'",
                    "4. Select your bridge and authenticate"
                ]
            elif device.category == DeviceCategory.HUB:
                integration["setup_steps"] = [
                    f"1. Device found at {device.ip}",
                    "2. Check Home Assistant integrations for this device",
                    "3. Follow manufacturer-specific setup"
                ]
            else:
                integration["setup_steps"] = [
                    "1. This device may need manual configuration",
                    "2. Check if Home Assistant has an integration",
                    f"3. Device IP: {device.ip}"
                ]
            
            integrations.append(integration)
        
        return integrations


# Singleton instance
_discovery: Optional[IoTDiscovery] = None


def get_discovery() -> IoTDiscovery:
    """Get or create the IoT discovery singleton"""
    global _discovery
    if _discovery is None:
        _discovery = IoTDiscovery()
    return _discovery


async def discover_devices() -> List[DiscoveredDevice]:
    """Convenience function to discover all devices"""
    discovery = get_discovery()
    return await discovery.scan_network()
