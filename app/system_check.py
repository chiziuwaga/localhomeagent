"""
System Hardware Check Module
Sprint 6: System requirements verification for Local Home Agent

Provides hardware detection and requirements verification API.
"""

import platform
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RequirementStatus(Enum):
    """Status of a requirement check"""
    PASS = "pass"
    WARN = "warn"  # Below recommended but above minimum
    FAIL = "fail"  # Below minimum


@dataclass
class SystemRequirements:
    """System requirements configuration"""
    ram_minimum_gb: float = 8.0
    ram_recommended_gb: float = 16.0
    cpu_cores_minimum: int = 4
    cpu_cores_recommended: int = 8
    disk_minimum_gb: float = 5.0
    disk_recommended_gb: float = 20.0


@dataclass
class HardwareInfo:
    """Detected hardware information"""
    ram_total_gb: float
    ram_available_gb: float
    cpu_cores: int
    cpu_name: str
    disk_free_gb: float
    disk_total_gb: float
    os_name: str
    os_version: str
    python_version: str


@dataclass
class RequirementCheck:
    """Result of a single requirement check"""
    name: str
    status: RequirementStatus
    current: float
    minimum: float
    recommended: float
    unit: str
    message: str


class SystemChecker:
    """System hardware detection and requirements verification"""
    
    def __init__(self, requirements: Optional[SystemRequirements] = None):
        self.requirements = requirements or SystemRequirements()
    
    def get_hardware_info(self) -> HardwareInfo:
        """Detect current system hardware"""
        try:
            import psutil
            
            # RAM
            mem = psutil.virtual_memory()
            ram_total_gb = mem.total / (1024 ** 3)
            ram_available_gb = mem.available / (1024 ** 3)
            
            # CPU
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
            cpu_name = platform.processor() or "Unknown"
            
            # Disk (check root or home directory)
            home_path = os.path.expanduser("~")
            disk = psutil.disk_usage(home_path)
            disk_free_gb = disk.free / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            
        except ImportError:
            # Fallback if psutil not available
            logger.warning("psutil not available, using fallback detection")
            ram_total_gb = 8.0  # Assume minimum
            ram_available_gb = 4.0
            cpu_cores = os.cpu_count() or 4
            cpu_name = platform.processor() or "Unknown"
            disk_free_gb = 10.0
            disk_total_gb = 100.0
        
        return HardwareInfo(
            ram_total_gb=round(ram_total_gb, 1),
            ram_available_gb=round(ram_available_gb, 1),
            cpu_cores=cpu_cores,
            cpu_name=cpu_name,
            disk_free_gb=round(disk_free_gb, 1),
            disk_total_gb=round(disk_total_gb, 1),
            os_name=platform.system(),
            os_version=platform.version(),
            python_version=platform.python_version()
        )
    
    def check_requirement(
        self,
        name: str,
        current: float,
        minimum: float,
        recommended: float,
        unit: str
    ) -> RequirementCheck:
        """Check a single requirement"""
        if current >= recommended:
            status = RequirementStatus.PASS
            message = f"Exceeds recommended ({recommended} {unit})"
        elif current >= minimum:
            status = RequirementStatus.WARN
            message = f"Meets minimum, below recommended ({recommended} {unit})"
        else:
            status = RequirementStatus.FAIL
            message = f"Below minimum requirement ({minimum} {unit})"
        
        return RequirementCheck(
            name=name,
            status=status,
            current=current,
            minimum=minimum,
            recommended=recommended,
            unit=unit,
            message=message
        )
    
    def check_all_requirements(self) -> Dict[str, Any]:
        """Check all system requirements"""
        hw = self.get_hardware_info()
        reqs = self.requirements
        
        checks = [
            self.check_requirement(
                "RAM",
                hw.ram_total_gb,
                reqs.ram_minimum_gb,
                reqs.ram_recommended_gb,
                "GB"
            ),
            self.check_requirement(
                "CPU Cores",
                float(hw.cpu_cores),
                float(reqs.cpu_cores_minimum),
                float(reqs.cpu_cores_recommended),
                "cores"
            ),
            self.check_requirement(
                "Disk Space",
                hw.disk_free_gb,
                reqs.disk_minimum_gb,
                reqs.disk_recommended_gb,
                "GB"
            ),
        ]
        
        # Overall status
        has_fail = any(c.status == RequirementStatus.FAIL for c in checks)
        has_warn = any(c.status == RequirementStatus.WARN for c in checks)
        
        if has_fail:
            overall_status = "fail"
            overall_message = "System does not meet minimum requirements"
        elif has_warn:
            overall_status = "warn"
            overall_message = "System meets minimum but not recommended requirements"
        else:
            overall_status = "pass"
            overall_message = "System meets all recommended requirements"
        
        return {
            "meets_requirements": not has_fail,
            "meets_recommended": not has_fail and not has_warn,
            "overall_status": overall_status,
            "overall_message": overall_message,
            "hardware": {
                "ram_total_gb": hw.ram_total_gb,
                "ram_available_gb": hw.ram_available_gb,
                "cpu_cores": hw.cpu_cores,
                "cpu_name": hw.cpu_name,
                "disk_free_gb": hw.disk_free_gb,
                "disk_total_gb": hw.disk_total_gb,
                "os": f"{hw.os_name} {hw.os_version}",
                "python_version": hw.python_version
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "current": c.current,
                    "minimum": c.minimum,
                    "recommended": c.recommended,
                    "unit": c.unit,
                    "message": c.message
                }
                for c in checks
            ]
        }


# Singleton instance
_system_checker: Optional[SystemChecker] = None


def get_system_checker() -> SystemChecker:
    """Get or create system checker instance"""
    global _system_checker
    if _system_checker is None:
        _system_checker = SystemChecker()
    return _system_checker


def create_system_routes():
    """Create FastAPI routes for system check"""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/system", tags=["system"])
    checker = get_system_checker()
    
    @router.get("/check")
    async def check_system_requirements():
        """
        Check if system meets hardware requirements.
        
        Returns:
            - meets_requirements: bool - True if minimum requirements met
            - meets_recommended: bool - True if recommended requirements met
            - hardware: dict - Detected hardware info
            - checks: list - Individual requirement check results
        """
        return checker.check_all_requirements()
    
    @router.get("/hardware")
    async def get_hardware_info():
        """Get detected hardware information without requirement checks"""
        hw = checker.get_hardware_info()
        return {
            "ram_total_gb": hw.ram_total_gb,
            "ram_available_gb": hw.ram_available_gb,
            "cpu_cores": hw.cpu_cores,
            "cpu_name": hw.cpu_name,
            "disk_free_gb": hw.disk_free_gb,
            "disk_total_gb": hw.disk_total_gb,
            "os": f"{hw.os_name} {hw.os_version}",
            "python_version": hw.python_version
        }
    
    @router.get("/requirements")
    async def get_requirements():
        """Get the system requirements thresholds"""
        reqs = checker.requirements
        return {
            "ram": {
                "minimum_gb": reqs.ram_minimum_gb,
                "recommended_gb": reqs.ram_recommended_gb
            },
            "cpu": {
                "minimum_cores": reqs.cpu_cores_minimum,
                "recommended_cores": reqs.cpu_cores_recommended
            },
            "disk": {
                "minimum_gb": reqs.disk_minimum_gb,
                "recommended_gb": reqs.disk_recommended_gb
            }
        }

    @router.get("/recommend-model")
    async def recommend_model():
        """
        Recommend an Ollama model based on detected hardware.

        Mirrors the client-side detection in client/src/pages/LocalAgentDownload.tsx
        but runs server-side using psutil so the agent can self-diagnose without
        relying on browser APIs (which underestimate RAM and can't see the GPU
        when the agent runs headless on a NUC / Pi / server).

        Tier ladder (RAM-driven; GPU detection on Windows/Mac is best-effort):
            >= 16 GB + GPU  -> llama3.1:8b   (excellent)
            >= 12 GB + GPU  -> mistral:7b    (good)
            >=  8 GB        -> llama3.2:3b   (good — recommended baseline)
            >=  4 cores     -> phi3:mini     (basic)
            otherwise       -> llama3.2:1b   (basic — last resort)
        """
        hw = checker.get_hardware_info()
        gpu = _detect_gpu()

        ram = hw.ram_total_gb
        cores = hw.cpu_cores
        has_gpu = gpu["type"] in ("nvidia", "amd", "apple")

        if has_gpu and ram >= 16:
            model = "llama3.1:8b"
            quality = "excellent"
            reason = "GPU + 16GB+ RAM → run a higher-quality 8B model"
        elif has_gpu and ram >= 12:
            model = "mistral:7b"
            quality = "good"
            reason = "GPU + 12GB+ RAM → 7B model with strong reasoning"
        elif ram >= 8 or (has_gpu and ram >= 6):
            model = "llama3.2:3b"
            quality = "good"
            reason = "8GB+ RAM → balanced 3B model recommended for most users"
        elif cores >= 4:
            model = "phi3:mini"
            quality = "basic"
            reason = "Limited RAM but 4+ cores → small but capable phi3 model"
        else:
            model = "llama3.2:1b"
            quality = "basic"
            reason = "Constrained hardware → smallest viable model"

        return {
            "recommended_model": model,
            "quality": quality,
            "reason": reason,
            "ollama_pull_command": f"ollama pull {model}",
            "hardware": {
                "ram_total_gb": hw.ram_total_gb,
                "ram_available_gb": hw.ram_available_gb,
                "cpu_cores": hw.cpu_cores,
                "gpu": gpu,
                "os": f"{hw.os_name} {hw.os_version}",
            },
            "alternatives": [
                {"model": "llama3.2:1b", "size_gb": 1.3, "quality": "basic"},
                {"model": "phi3:mini", "size_gb": 2.3, "quality": "basic"},
                {"model": "llama3.2:3b", "size_gb": 2.0, "quality": "good"},
                {"model": "mistral:7b", "size_gb": 4.1, "quality": "good"},
                {"model": "llama3.1:8b", "size_gb": 4.7, "quality": "excellent"},
            ],
        }

    return router


def _detect_gpu() -> Dict[str, Any]:
    """
    Best-effort GPU detection.

    - NVIDIA: nvidia-smi (universally available with the driver on win/linux)
    - macOS:  detect Apple Silicon via platform.processor()
    - Otherwise: return type='unknown'

    Wrapped in try/except — never raises.
    """
    import platform as _platform
    import subprocess

    info: Dict[str, Any] = {"type": "unknown", "name": "Unknown", "vram_gb": None}

    # Apple Silicon (unified memory — counts as GPU for our purposes)
    machine = (_platform.machine() or "").lower()
    if _platform.system() == "Darwin" and ("arm" in machine or "aarch" in machine):
        info["type"] = "apple"
        info["name"] = "Apple Silicon"
        return info

    # NVIDIA via nvidia-smi
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            first = out.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            if len(parts) >= 2:
                info["type"] = "nvidia"
                info["name"] = parts[0]
                try:
                    info["vram_gb"] = round(int(parts[1]) / 1024, 1)
                except ValueError:
                    pass
                return info
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # AMD via rocm-smi (linux mostly)
    try:
        out = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and "GPU" in out.stdout:
            info["type"] = "amd"
            info["name"] = "AMD GPU (rocm)"
            return info
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return info
