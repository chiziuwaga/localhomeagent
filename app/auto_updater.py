"""
Auto-Update Mechanism for Local Home Agent (F4.6.9)
Checks for updates from GitHub releases and downloads/installs them
"""

import asyncio
import aiohttp
import json
import logging
import os
import sys
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import hashlib

logger = logging.getLogger(__name__)

# GitHub repository info
GITHUB_OWNER = "Fix-It-For-Me-AI"
GITHUB_REPO = "local-home-agent"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


@dataclass
class ReleaseInfo:
    """Information about a GitHub release"""
    version: str
    tag_name: str
    name: str
    body: str
    published_at: str
    download_url: Optional[str]
    size: int
    sha256: Optional[str]


class AutoUpdater:
    """
    Manages automatic updates for Local Home Agent
    
    Features:
    - Check for updates from GitHub releases
    - Download updates with progress tracking
    - Verify download integrity (SHA256)
    - Apply updates with backup/rollback
    - Schedule automatic update checks
    """
    
    def __init__(self, current_version: str = "1.0.0"):
        self.current_version = current_version
        self.config_dir = Path(os.environ.get('APPDATA', '~')) / "LocalHomeAgent"
        self.config_file = self.config_dir / "update_config.json"
        self.update_dir = self.config_dir / "updates"
        self.backup_dir = self.config_dir / "backups"
        
        # Create directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.update_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load update configuration"""
        default_config = {
            "auto_check": True,
            "check_interval_hours": 24,
            "auto_download": False,
            "auto_install": False,
            "last_check": None,
            "skipped_versions": [],
            "update_channel": "stable"  # stable, beta, nightly
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    saved = json.load(f)
                    default_config.update(saved)
            except Exception as e:
                logger.warning(f"Failed to load update config: {e}")
        
        return default_config
    
    def save_config(self):
        """Save update configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _parse_version(self, version: str) -> Tuple[int, ...]:
        """Parse version string into tuple for comparison"""
        # Remove 'v' prefix if present
        version = version.lstrip('v')
        parts = version.split('-')[0].split('.')  # Handle pre-release tags
        return tuple(int(p) for p in parts if p.isdigit())
    
    def _is_newer_version(self, remote_version: str) -> bool:
        """Check if remote version is newer than current"""
        try:
            current = self._parse_version(self.current_version)
            remote = self._parse_version(remote_version)
            return remote > current
        except Exception as e:
            logger.warning(f"Version comparison failed: {e}")
            return False
    
    async def check_for_updates(self, force: bool = False) -> Optional[ReleaseInfo]:
        """
        Check GitHub for available updates
        
        Args:
            force: Bypass check interval
            
        Returns:
            ReleaseInfo if update available, None otherwise
        """
        # Check interval
        if not force and self.config.get("last_check"):
            last_check = datetime.fromisoformat(self.config["last_check"])
            interval = timedelta(hours=self.config.get("check_interval_hours", 24))
            if datetime.now() - last_check < interval:
                logger.debug("Skipping update check - within interval")
                return None
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/vnd.github.v3+json"}
                
                async with session.get(RELEASES_URL, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning(f"Failed to check updates: HTTP {resp.status}")
                        return None
                    
                    data = await resp.json()
            
            # Update last check time
            self.config["last_check"] = datetime.now().isoformat()
            self.save_config()
            
            # Parse release info
            tag = data.get("tag_name", "")
            
            # Check if newer
            if not self._is_newer_version(tag):
                logger.info(f"Already on latest version: {self.current_version}")
                return None
            
            # Check if skipped
            if tag in self.config.get("skipped_versions", []):
                logger.info(f"Version {tag} was skipped by user")
                return None
            
            # Find correct asset for platform
            download_url = None
            size = 0
            sha256 = None
            
            platform = sys.platform
            arch = "64" if sys.maxsize > 2**32 else "32"
            
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                
                # Match platform
                if platform == "win32" and "windows" in name:
                    if arch in name or "64" in name:
                        download_url = asset.get("browser_download_url")
                        size = asset.get("size", 0)
                        break
                elif platform == "darwin" and "macos" in name:
                    download_url = asset.get("browser_download_url")
                    size = asset.get("size", 0)
                    break
                elif platform.startswith("linux") and "linux" in name:
                    download_url = asset.get("browser_download_url")
                    size = asset.get("size", 0)
                    break
            
            # Check for SHA256 file
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".sha256"):
                    sha256_url = asset.get("browser_download_url")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(sha256_url, timeout=10) as resp:
                            if resp.status == 200:
                                sha256 = (await resp.text()).strip().split()[0]
                    break
            
            return ReleaseInfo(
                version=tag.lstrip('v'),
                tag_name=tag,
                name=data.get("name", tag),
                body=data.get("body", ""),
                published_at=data.get("published_at", ""),
                download_url=download_url,
                size=size,
                sha256=sha256
            )
            
        except asyncio.TimeoutError:
            logger.warning("Update check timed out")
            return None
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None
    
    async def download_update(
        self,
        release: ReleaseInfo,
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """
        Download update package
        
        Args:
            release: Release information
            progress_callback: Called with (downloaded, total) bytes
            
        Returns:
            Path to downloaded file, or None on failure
        """
        if not release.download_url:
            logger.error("No download URL available")
            return None
        
        download_path = self.update_dir / f"update-{release.version}.zip"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(release.download_url, timeout=300) as resp:
                    if resp.status != 200:
                        logger.error(f"Download failed: HTTP {resp.status}")
                        return None
                    
                    total = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    
                    with open(download_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback:
                                progress_callback(downloaded, total)
            
            # Verify SHA256 if available
            if release.sha256:
                sha256 = hashlib.sha256()
                with open(download_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha256.update(chunk)
                
                if sha256.hexdigest().lower() != release.sha256.lower():
                    logger.error("SHA256 verification failed!")
                    download_path.unlink()
                    return None
                
                logger.info("SHA256 verification passed")
            
            logger.info(f"Downloaded update to {download_path}")
            return download_path
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if download_path.exists():
                download_path.unlink()
            return None
    
    def create_backup(self) -> Optional[Path]:
        """Create backup of current installation"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup-{self.current_version}-{timestamp}.zip"
        
        try:
            # Get installation directory
            if getattr(sys, 'frozen', False):
                install_dir = Path(sys.executable).parent
            else:
                install_dir = Path(__file__).parent.parent
            
            # Create backup zip
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in install_dir.rglob('*'):
                    if file.is_file() and 'backup' not in str(file):
                        arcname = file.relative_to(install_dir)
                        zf.write(file, arcname)
            
            logger.info(f"Created backup at {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None
    
    def apply_update(self, update_path: Path, backup_path: Optional[Path] = None) -> bool:
        """
        Apply downloaded update
        
        This creates a batch script that:
        1. Waits for current process to exit
        2. Extracts update
        3. Restarts application
        """
        if not update_path.exists():
            logger.error("Update file not found")
            return False
        
        try:
            # Get installation directory
            if getattr(sys, 'frozen', False):
                install_dir = Path(sys.executable).parent
                exe_path = sys.executable
            else:
                logger.warning("Cannot auto-update in development mode")
                return False
            
            # Create update script
            script_path = self.update_dir / "apply_update.bat"

            # Build the rollback command outside the f-string —
            # Python 3.11 doesn't allow backslashes inside f-string {...} parts.
            if backup_path:
                rollback_cmd = (
                    'powershell -Command "Expand-Archive -Path \''
                    + str(backup_path)
                    + "' -DestinationPath '"
                    + str(install_dir)
                    + "' -Force\""
                )
            else:
                rollback_cmd = "echo No backup available"

            script_content = f'''@echo off
echo Waiting for application to close...
timeout /t 3 /nobreak > nul

echo Extracting update...
powershell -Command "Expand-Archive -Path '{update_path}' -DestinationPath '{install_dir}' -Force"

if %ERRORLEVEL% NEQ 0 (
    echo Update failed! Restoring backup...
    {rollback_cmd}
    exit /b 1
)

echo Update complete! Restarting application...
start "" "{exe_path}"

echo Cleaning up...
del "{update_path}"
del "%~f0"
'''
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Start update script and exit
            subprocess.Popen(
                ['cmd', '/c', str(script_path)],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            logger.info("Update script started, application will restart...")
            return True
            
        except Exception as e:
            logger.error(f"Apply update failed: {e}")
            return False
    
    def skip_version(self, version: str):
        """Mark a version to be skipped"""
        if version not in self.config.get("skipped_versions", []):
            self.config.setdefault("skipped_versions", []).append(version)
            self.save_config()
    
    async def auto_update_check(self):
        """Run automatic update check in background"""
        if not self.config.get("auto_check", True):
            return
        
        release = await self.check_for_updates()
        
        if release:
            logger.info(f"Update available: {release.version}")
            
            if self.config.get("auto_download", False):
                update_path = await self.download_update(release)
                
                if update_path and self.config.get("auto_install", False):
                    backup = self.create_backup()
                    self.apply_update(update_path, backup)
            
            return release
        
        return None


class UpdateNotifier:
    """UI-friendly update notifications"""
    
    def __init__(self, updater: AutoUpdater):
        self.updater = updater
        self.pending_update: Optional[ReleaseInfo] = None
    
    def get_update_status(self) -> Dict[str, Any]:
        """Get current update status for UI"""
        return {
            "current_version": self.updater.current_version,
            "pending_update": {
                "version": self.pending_update.version,
                "name": self.pending_update.name,
                "body": self.pending_update.body,
                "download_url": self.pending_update.download_url,
                "size": self.pending_update.size
            } if self.pending_update else None,
            "auto_check": self.updater.config.get("auto_check", True),
            "last_check": self.updater.config.get("last_check"),
            "update_channel": self.updater.config.get("update_channel", "stable")
        }
    
    def format_release_notes(self, release: ReleaseInfo) -> str:
        """Format release notes for display"""
        import re
        
        body = release.body
        
        # Convert markdown headers
        body = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', body, flags=re.MULTILINE)
        body = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', body, flags=re.MULTILINE)
        
        # Convert lists
        body = re.sub(r'^- (.*?)$', r'<li>\1</li>', body, flags=re.MULTILINE)
        
        # Convert bold/italic
        body = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', body)
        body = re.sub(r'\*(.*?)\*', r'<em>\1</em>', body)
        
        return body


# FastAPI routes for update management
def register_update_routes(app, updater: AutoUpdater):
    """Register update API routes"""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/updates", tags=["updates"])
    notifier = UpdateNotifier(updater)
    
    @router.get("/status")
    async def get_update_status():
        return notifier.get_update_status()
    
    @router.post("/check")
    async def check_updates():
        release = await updater.check_for_updates(force=True)
        if release:
            notifier.pending_update = release
            return {"available": True, "release": release.__dict__}
        return {"available": False}
    
    @router.post("/download")
    async def download_update():
        if not notifier.pending_update:
            return {"error": "No pending update"}
        
        path = await updater.download_update(notifier.pending_update)
        return {"success": path is not None, "path": str(path) if path else None}
    
    @router.post("/install")
    async def install_update():
        if not notifier.pending_update:
            return {"error": "No pending update"}
        
        update_path = updater.update_dir / f"update-{notifier.pending_update.version}.zip"
        if not update_path.exists():
            return {"error": "Update not downloaded"}
        
        backup = updater.create_backup()
        success = updater.apply_update(update_path, backup)
        return {"success": success, "message": "Application will restart" if success else "Install failed"}
    
    @router.post("/skip/{version}")
    async def skip_version(version: str):
        updater.skip_version(version)
        return {"success": True}
    
    @router.put("/config")
    async def update_config(config: Dict[str, Any]):
        updater.config.update(config)
        updater.save_config()
        return {"success": True}
    
    app.include_router(router)


if __name__ == "__main__":
    # Test update check
    async def test():
        updater = AutoUpdater(current_version="0.9.0")  # Old version for testing
        release = await updater.check_for_updates(force=True)
        
        if release:
            print(f"Update available: {release.version}")
            print(f"Download URL: {release.download_url}")
            print(f"Size: {release.size / 1024 / 1024:.1f} MB")
        else:
            print("No update available")
    
    asyncio.run(test())
