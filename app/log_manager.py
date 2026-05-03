"""
Log Management System
P5: LM1 - Structured logging with rotation, viewer, and export

Features:
- LM1.1: Log rotation (daily files, 7-day retention)
- LM1.2: Structured logging (JSON format)
- LM1.3: Log viewer UI in admin panel
- LM1.4: Log export functionality
- LM1.5: Log level filtering
- LM1.6: Real-time log streaming
- LM1.7: Log search functionality
- LM1.8: Log analytics
- LM1.9: Automatic log compression
- LM1.10: Sensitive data redaction
"""

import asyncio
import gzip
import json
import logging
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, AsyncGenerator, Callable
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import io
import zipfile

# ============================================================================
# ENUMS & TYPES
# ============================================================================

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    SYSTEM = "system"
    SECURITY = "security"
    ENERGY = "energy"
    DEVICE = "device"
    CHAT = "chat"
    AUTOMATION = "automation"
    API = "api"
    BLUETOOTH = "bluetooth"
    NETWORK = "network"


# Patterns for sensitive data redaction
SENSITIVE_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
    (r'\b\d{16}\b', '[CARD_REDACTED]'),
    (r'password["\']?\s*[:=]\s*["\']?[^"\'}\s]+', 'password=[REDACTED]'),
    (r'token["\']?\s*[:=]\s*["\']?[^"\'}\s]+', 'token=[REDACTED]'),
    (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'}\s]+', 'api_key=[REDACTED]'),
    (r'secret["\']?\s*[:=]\s*["\']?[^"\'}\s]+', 'secret=[REDACTED]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
]


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    source: str
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "category": self.category.value,
            "message": self.message,
            "source": self.source,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "metadata": self.metadata,
            "request_id": self.request_id
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            level=LogLevel(data["level"]),
            category=LogCategory(data["category"]),
            message=data["message"],
            source=data["source"],
            user_id=data.get("user_id"),
            device_id=data.get("device_id"),
            metadata=data.get("metadata"),
            request_id=data.get("request_id")
        )


@dataclass
class LogStats:
    """Log statistics"""
    total_entries: int
    entries_by_level: Dict[str, int]
    entries_by_category: Dict[str, int]
    error_rate: float
    entries_per_hour: Dict[str, int]
    top_sources: List[tuple]
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]


# ============================================================================
# LOG MANAGER
# ============================================================================

class LogManager:
    """
    Central log management system with rotation, compression, and streaming.
    """
    
    def __init__(
        self,
        log_dir: Path = Path("logs"),
        retention_days: int = 7,
        max_file_size_mb: int = 50,
        enable_compression: bool = True,
        enable_redaction: bool = True
    ):
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.enable_compression = enable_compression
        self.enable_redaction = enable_redaction
        
        # Current log file
        self.current_date = datetime.now().date()
        self.current_file: Optional[Path] = None
        
        # WebSocket connections for live streaming
        self.streaming_clients: List[WebSocket] = []
        
        # In-memory buffer for recent logs
        self.recent_logs: List[LogEntry] = []
        self.max_recent_logs = 1000
        
        # Initialize
        self._ensure_log_dir()
        self._setup_current_file()
        self._cleanup_old_logs()
    
    def _ensure_log_dir(self):
        """Ensure log directory exists"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_current_file(self):
        """Setup current log file for the day"""
        date_str = self.current_date.strftime("%Y-%m-%d")
        self.current_file = self.log_dir / f"local_agent_{date_str}.jsonl"
    
    def _rotate_if_needed(self):
        """Rotate log file if date changed or size exceeded"""
        now_date = datetime.now().date()
        
        # Check date change
        if now_date != self.current_date:
            self._compress_old_file()
            self.current_date = now_date
            self._setup_current_file()
            return
        
        # Check file size
        if self.current_file and self.current_file.exists():
            if self.current_file.stat().st_size > self.max_file_size_bytes:
                # Add sequence number
                base_name = self.current_file.stem
                seq = 1
                while True:
                    new_name = f"{base_name}_{seq}.jsonl"
                    new_path = self.log_dir / new_name
                    if not new_path.exists():
                        self.current_file.rename(new_path)
                        if self.enable_compression:
                            self._compress_file(new_path)
                        break
                    seq += 1
                self._setup_current_file()
    
    def _compress_old_file(self):
        """Compress the previous day's log file"""
        if not self.enable_compression or not self.current_file:
            return
        
        if self.current_file.exists():
            self._compress_file(self.current_file)
    
    def _compress_file(self, file_path: Path):
        """Compress a log file with gzip"""
        try:
            gz_path = file_path.with_suffix(file_path.suffix + ".gz")
            with open(file_path, "rb") as f_in:
                with gzip.open(gz_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            file_path.unlink()
            logging.info(f"Compressed log file: {gz_path.name}")
        except Exception as e:
            logging.error(f"Failed to compress {file_path}: {e}")
    
    def _cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        
        for file_path in self.log_dir.glob("local_agent_*.jsonl*"):
            try:
                # Extract date from filename
                name = file_path.stem.replace(".jsonl", "")
                parts = name.split("_")
                if len(parts) >= 3:
                    date_str = f"{parts[2]}"
                    if len(parts) >= 4:
                        date_str = f"{parts[2]}"
                    try:
                        file_date = datetime.strptime(date_str, "%Y-%m-%d")
                        if file_date < cutoff:
                            file_path.unlink()
                            logging.info(f"Removed old log file: {file_path.name}")
                    except ValueError:
                        pass
            except Exception as e:
                logging.error(f"Error cleaning up {file_path}: {e}")
    
    def _redact_sensitive(self, message: str) -> str:
        """Redact sensitive data from message"""
        if not self.enable_redaction:
            return message
        
        for pattern, replacement in SENSITIVE_PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        
        return message
    
    # ========================================================================
    # LOGGING
    # ========================================================================
    
    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        source: str = "system",
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        """Write a structured log entry"""
        self._rotate_if_needed()
        
        # Redact sensitive data
        message = self._redact_sensitive(message)
        if metadata:
            metadata = json.loads(self._redact_sensitive(json.dumps(metadata)))
        
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            source=source,
            user_id=user_id,
            device_id=device_id,
            metadata=metadata,
            request_id=request_id
        )
        
        # Write to file
        if self.current_file:
            with open(self.current_file, "a") as f:
                f.write(entry.to_json() + "\n")
        
        # Add to recent logs buffer
        self.recent_logs.append(entry)
        if len(self.recent_logs) > self.max_recent_logs:
            self.recent_logs.pop(0)
        
        # Stream to connected clients
        asyncio.create_task(self._broadcast_log(entry))
    
    async def _broadcast_log(self, entry: LogEntry):
        """Broadcast log entry to all streaming clients"""
        if not self.streaming_clients:
            return
        
        message = entry.to_json()
        disconnected = []
        
        for client in self.streaming_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)
        
        for client in disconnected:
            self.streaming_clients.remove(client)
    
    def info(self, category: LogCategory, message: str, **kwargs):
        self.log(LogLevel.INFO, category, message, **kwargs)
    
    def warning(self, category: LogCategory, message: str, **kwargs):
        self.log(LogLevel.WARNING, category, message, **kwargs)
    
    def error(self, category: LogCategory, message: str, **kwargs):
        self.log(LogLevel.ERROR, category, message, **kwargs)
    
    def debug(self, category: LogCategory, message: str, **kwargs):
        self.log(LogLevel.DEBUG, category, message, **kwargs)
    
    def critical(self, category: LogCategory, message: str, **kwargs):
        self.log(LogLevel.CRITICAL, category, message, **kwargs)
    
    # ========================================================================
    # READING & SEARCHING
    # ========================================================================
    
    def get_recent_logs(
        self,
        limit: int = 100,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None
    ) -> List[LogEntry]:
        """Get recent logs from memory buffer"""
        logs = self.recent_logs.copy()
        
        if level:
            logs = [l for l in logs if l.level == level]
        if category:
            logs = [l for l in logs if l.category == category]
        
        return logs[-limit:]
    
    def search_logs(
        self,
        query: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        limit: int = 500
    ) -> List[LogEntry]:
        """Search logs across files"""
        results = []
        query_lower = query.lower()
        
        # Determine date range
        if not start_date:
            start_date = datetime.now() - timedelta(days=self.retention_days)
        if not end_date:
            end_date = datetime.now()
        
        # Get relevant files
        for file_path in sorted(self.log_dir.glob("local_agent_*.jsonl*")):
            if len(results) >= limit:
                break
            
            try:
                # Read file (handle gzip)
                if file_path.suffix == ".gz":
                    with gzip.open(file_path, "rt") as f:
                        lines = f.readlines()
                else:
                    with open(file_path, "r") as f:
                        lines = f.readlines()
                
                for line in lines:
                    if len(results) >= limit:
                        break
                    
                    try:
                        data = json.loads(line.strip())
                        entry = LogEntry.from_dict(data)
                        
                        # Apply filters
                        if level and entry.level != level:
                            continue
                        if category and entry.category != category:
                            continue
                        if entry.timestamp < start_date or entry.timestamp > end_date:
                            continue
                        if query_lower not in entry.message.lower():
                            continue
                        
                        results.append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception as e:
                logging.error(f"Error reading {file_path}: {e}")
        
        return results
    
    def get_logs_for_date(self, date: datetime.date) -> List[LogEntry]:
        """Get all logs for a specific date"""
        date_str = date.strftime("%Y-%m-%d")
        results = []
        
        for file_path in self.log_dir.glob(f"local_agent_{date_str}*.jsonl*"):
            try:
                if file_path.suffix == ".gz":
                    with gzip.open(file_path, "rt") as f:
                        lines = f.readlines()
                else:
                    with open(file_path, "r") as f:
                        lines = f.readlines()
                
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        entry = LogEntry.from_dict(data)
                        results.append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception as e:
                logging.error(f"Error reading {file_path}: {e}")
        
        return results
    
    # ========================================================================
    # ANALYTICS
    # ========================================================================
    
    def get_stats(self, hours: int = 24) -> LogStats:
        """Get log statistics for the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        entries = []
        for entry in self.recent_logs:
            if entry.timestamp >= cutoff:
                entries.append(entry)
        
        # Also search files if needed
        if len(entries) < 100:
            file_entries = self.search_logs(
                query="",
                start_date=cutoff,
                limit=1000
            )
            entries.extend(file_entries)
        
        # Calculate stats
        by_level = defaultdict(int)
        by_category = defaultdict(int)
        by_hour = defaultdict(int)
        sources = defaultdict(int)
        
        for entry in entries:
            by_level[entry.level.value] += 1
            by_category[entry.category.value] += 1
            hour_key = entry.timestamp.strftime("%Y-%m-%d %H:00")
            by_hour[hour_key] += 1
            sources[entry.source] += 1
        
        error_count = by_level.get("ERROR", 0) + by_level.get("CRITICAL", 0)
        total = len(entries)
        
        return LogStats(
            total_entries=total,
            entries_by_level=dict(by_level),
            entries_by_category=dict(by_category),
            error_rate=error_count / total if total > 0 else 0,
            entries_per_hour=dict(by_hour),
            top_sources=sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10],
            oldest_entry=min((e.timestamp for e in entries), default=None),
            newest_entry=max((e.timestamp for e in entries), default=None)
        )
    
    # ========================================================================
    # EXPORT
    # ========================================================================
    
    def export_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "jsonl"
    ) -> bytes:
        """Export logs as a downloadable file"""
        entries = self.search_logs(
            query="",
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        if format == "jsonl":
            output = "\n".join(e.to_json() for e in entries)
            return output.encode("utf-8")
        
        elif format == "json":
            output = json.dumps([e.to_dict() for e in entries], indent=2)
            return output.encode("utf-8")
        
        elif format == "csv":
            import csv
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["timestamp", "level", "category", "source", "message", "user_id", "device_id"])
            for e in entries:
                writer.writerow([
                    e.timestamp.isoformat(),
                    e.level.value,
                    e.category.value,
                    e.source,
                    e.message,
                    e.user_id or "",
                    e.device_id or ""
                ])
            return buffer.getvalue().encode("utf-8")
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def export_all_as_zip(self) -> bytes:
        """Export all log files as a ZIP archive"""
        buffer = io.BytesIO()
        
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(self.log_dir.glob("local_agent_*.jsonl*")):
                if file_path.suffix == ".gz":
                    # Decompress for zip
                    with gzip.open(file_path, "rb") as f:
                        content = f.read()
                    zf.writestr(file_path.stem, content)
                else:
                    zf.write(file_path, file_path.name)
        
        return buffer.getvalue()
    
    # ========================================================================
    # STREAMING
    # ========================================================================
    
    def add_streaming_client(self, websocket: WebSocket):
        """Add a WebSocket client for live log streaming"""
        self.streaming_clients.append(websocket)
    
    def remove_streaming_client(self, websocket: WebSocket):
        """Remove a WebSocket client"""
        if websocket in self.streaming_clients:
            self.streaming_clients.remove(websocket)


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_log_manager: Optional[LogManager] = None

def get_log_manager() -> LogManager:
    """Get or create the global log manager"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


# ============================================================================
# INTEGRATION WITH STANDARD LOGGING
# ============================================================================

class StructuredLogHandler(logging.Handler):
    """Custom handler to integrate with LogManager"""
    
    def __init__(self, log_manager: LogManager, category: LogCategory = LogCategory.SYSTEM):
        super().__init__()
        self.log_manager = log_manager
        self.category = category
    
    def emit(self, record: logging.LogRecord):
        level_map = {
            logging.DEBUG: LogLevel.DEBUG,
            logging.INFO: LogLevel.INFO,
            logging.WARNING: LogLevel.WARNING,
            logging.ERROR: LogLevel.ERROR,
            logging.CRITICAL: LogLevel.CRITICAL
        }
        
        level = level_map.get(record.levelno, LogLevel.INFO)
        message = self.format(record)
        
        self.log_manager.log(
            level=level,
            category=self.category,
            message=message,
            source=record.name
        )


def setup_logging_integration():
    """Setup integration between standard logging and LogManager"""
    manager = get_log_manager()
    handler = StructuredLogHandler(manager)
    handler.setLevel(logging.INFO)
    
    # Add to root logger
    logging.getLogger().addHandler(handler)


# ============================================================================
# API ROUTES
# ============================================================================

class LogSearchRequest(BaseModel):
    query: str = ""
    level: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 100


def create_log_routes() -> APIRouter:
    """Create FastAPI router for log management"""
    router = APIRouter(prefix="/logs", tags=["logs"])
    
    @router.get("/recent")
    async def get_recent_logs(
        limit: int = Query(100, le=1000),
        level: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Get recent logs from memory buffer"""
        manager = get_log_manager()
        
        level_enum = LogLevel(level) if level else None
        category_enum = LogCategory(category) if category else None
        
        logs = manager.get_recent_logs(limit, level_enum, category_enum)
        return {"logs": [l.to_dict() for l in logs]}
    
    @router.post("/search")
    async def search_logs(request: LogSearchRequest):
        """Search logs with filters"""
        manager = get_log_manager()
        
        level_enum = LogLevel(request.level) if request.level else None
        category_enum = LogCategory(request.category) if request.category else None
        start = datetime.fromisoformat(request.start_date) if request.start_date else None
        end = datetime.fromisoformat(request.end_date) if request.end_date else None
        
        logs = manager.search_logs(
            query=request.query,
            start_date=start,
            end_date=end,
            level=level_enum,
            category=category_enum,
            limit=request.limit
        )
        
        return {"logs": [l.to_dict() for l in logs], "count": len(logs)}
    
    @router.get("/stats")
    async def get_log_stats(hours: int = Query(24, le=168)):
        """Get log statistics"""
        manager = get_log_manager()
        stats = manager.get_stats(hours)
        
        return {
            "total_entries": stats.total_entries,
            "entries_by_level": stats.entries_by_level,
            "entries_by_category": stats.entries_by_category,
            "error_rate": stats.error_rate,
            "entries_per_hour": stats.entries_per_hour,
            "top_sources": [{"source": s, "count": c} for s, c in stats.top_sources],
            "oldest_entry": stats.oldest_entry.isoformat() if stats.oldest_entry else None,
            "newest_entry": stats.newest_entry.isoformat() if stats.newest_entry else None
        }
    
    @router.get("/export")
    async def export_logs(
        format: str = Query("jsonl", regex="^(jsonl|json|csv)$"),
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """Export logs in specified format"""
        manager = get_log_manager()
        
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        content = manager.export_logs(start, end, format)
        
        content_types = {
            "jsonl": "application/x-ndjson",
            "json": "application/json",
            "csv": "text/csv"
        }
        
        filename = f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_types[format],
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    @router.get("/export/zip")
    async def export_all_logs_zip():
        """Export all log files as ZIP"""
        manager = get_log_manager()
        content = manager.export_all_as_zip()
        
        filename = f"all_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    @router.get("/levels")
    async def get_log_levels():
        """Get available log levels"""
        return {"levels": [l.value for l in LogLevel]}
    
    @router.get("/categories")
    async def get_log_categories():
        """Get available log categories"""
        return {"categories": [c.value for c in LogCategory]}
    
    @router.websocket("/stream")
    async def stream_logs(websocket: WebSocket):
        """WebSocket endpoint for real-time log streaming"""
        await websocket.accept()
        
        manager = get_log_manager()
        manager.add_streaming_client(websocket)
        
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.remove_streaming_client(websocket)
    
    return router
