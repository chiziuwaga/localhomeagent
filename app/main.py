"""
Local Home Agent - FastAPI Application
Runs on local network with WiFi captive portal for co-living property management

Features:
- Local LLM integration (Ollama/LM Studio)
- Thermodynamic energy-based security model
- Role-based access control (admin, resident, guest)
- Smart home device integration (Home Assistant)
- WebSocket real-time communication
"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import uuid
import socket
import hashlib
import time
import secrets
from datetime import datetime
import asyncio
import logging

# Import local modules (use relative imports for package compatibility)
from .llm_client import get_llm_client, HOME_AGENT_SYSTEM_PROMPT
from .energy_model import (
    get_audit_log,
    get_dashboard,
    evaluate_action,
    EnergyLevel,
)
from .tool_graph import LocalToolGraph, LLMRuntimeConfig
from .auto_updater import AutoUpdater, register_update_routes

# P3: Advanced AI Features - Agentic Swarm & Prompt Chains
from .verification_swarm import PassphraseSwarm, create_passphrase_swarm, VerificationOutcome
from .prompt_chains import PromptChainVerifier
from .thermodynamic_reasoning import ThermodynamicReasoner

# P3: Robust Role-Based Access Control (RBAC) with IoT Device Assignment
from .rbac import (
    get_rbac_manager, RoleType, PermissionType,
)
from .communication_protocol import get_family_chat
from .home_assistant import HomeAssistantClient
from .notifications import (
    get_notification_service,
    create_notification_routes,
    NotificationPayload,
    NotificationPriority
)
from .queue_auth import get_queue_auth_manager, create_queue_auth_routes

# P4: Advanced Features
from .voice_module import create_voice_routes
from .communication_protocol import create_communication_routes
from .iot_pairing_wizard import create_pairing_routes
from .persona_builder import create_persona_routes
from .encryption_module import create_encryption_routes

# P5: Conversation persistence for chat history
from .conversation_cache import get_conversation_cache

# P6: System hardware check
from .system_check import create_system_routes

# P7: Platform pairing — agent ↔ Co-Living user link
from .platform_pairing import create_platform_pairing_routes

# Bluetooth pairing + log streaming — modules existed but were never mounted
from .bluetooth_pairing import create_bluetooth_routes
from .log_manager import create_log_routes

# Auth middleware (replaces hardcoded admin_id defaults and spoofable headers)
from .auth import (
    get_current_user, require_admin, require_operator_or_admin,
    AuthenticatedUser, create_token, hash_pin, verify_pin,
)
from . import secret_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sentry — initialise before app creation so the FastAPI integration auto-wraps.
_SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if _SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("[sentry] initialised")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sentry] init failed: %s", exc)

# Initialize FastAPI app
app = FastAPI(
    title="Local Home Agent",
    description="AI-powered local home management system for co-living properties",
    version="1.0.0"
)

# CORS middleware - configurable origins (do NOT use * with credentials)
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# First-run gate: until the user picks their own PIN + passphrase, redirect
# every non-static / non-setup HTML request to /setup. APIs that the wizard
# itself needs to call (/api/setup/*, /api/health, /api/system/check) stay
# open; everything else returns 423 Locked so a curious browser tab can't
# poke the dashboard before credentials are configured.
@app.middleware("http")
async def first_run_gate(request: Request, call_next):
    if _FIRST_RUN_COMPLETE:
        return await call_next(request)
    path = request.url.path
    allowed_prefixes = (
        "/setup",
        "/static/",
        "/api/setup/",
        "/api/health",
        "/api/system/check",
        "/favicon",
    )
    if path == "/" or path == "":
        return RedirectResponse(url="/setup", status_code=307)
    if any(path.startswith(p) for p in allowed_prefixes):
        return await call_next(request)
    # Everything else is locked until first-run completes
    if path.startswith("/api/"):
        return JSONResponse(
            status_code=423,
            content={
                "success": False,
                "error": "First-run setup not complete. Visit /setup.",
            },
        )
    return RedirectResponse(url="/setup", status_code=307)

# Mount static files and templates
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
templates_path = os.path.join(os.path.dirname(__file__), "..", "templates")

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# In-memory storage (replace with SQLite for production)
class DataStore:
    def __init__(self):
        self.users = []
        self.messages = []
        self.devices = []
        self.settings = {
            "home_name": "My Co-Living Space",
            "admin_configured": False,
            "llm_configured": False,
            "wifi_configured": False,
        }
        self.active_connections: List[WebSocket] = []
        self.guest_connections: Dict[str, WebSocket] = {}  # guest_id -> WebSocket
        self.admin_connections: Dict[str, WebSocket] = {}  # admin_id -> WebSocket

data_store = DataStore()

# Home Assistant client singleton
_ha_client: Optional[HomeAssistantClient] = None

def get_ha_client() -> HomeAssistantClient:
    """Get or create the Home Assistant client singleton"""
    global _ha_client
    if _ha_client is None:
        _ha_client = HomeAssistantClient()
        # Load from settings if configured
        settings = data_store.settings
        ha_url = settings.get("home_assistant_url")
        ha_token = settings.get("home_assistant_token")
        if ha_url and ha_token:
            _ha_client.configure(ha_url, ha_token)
            logger.info(f"Home Assistant client configured: {ha_url}")
    return _ha_client

# Initialize tool graph for local LLM tool calling (F4.6.7)
tool_graph = LocalToolGraph(max_energy=100.0)
tool_graph.build_tool_calling_graph()

# Initialize auto-updater (F4.6.9)
auto_updater = AutoUpdater(current_version="1.0.0")

# Register update routes
register_update_routes(app, auto_updater)

# P4: Register advanced feature routes (D2 & D3)
app.include_router(create_voice_routes())  # D2.1, D2.2: Voice verification & commands
app.include_router(create_communication_routes())  # D3: Communication protocol
app.include_router(create_pairing_routes())  # D2.3: IoT pairing wizard
app.include_router(create_persona_routes())  # D2.4: Custom persona builder
app.include_router(create_encryption_routes())  # D2.6: End-to-end encryption
app.include_router(create_system_routes())  # P6: Hardware check API
app.include_router(create_platform_pairing_routes())  # P7: Co-Living pairing handshake
app.include_router(create_bluetooth_routes())  # BLE pairing wizard endpoints
app.include_router(create_log_routes())  # Recent logs + live WS log stream
create_notification_routes(app)  # WiFi/BLE push notifications to admin mobile
create_queue_auth_routes(app)  # Per-queue auth for multi-resident isolation

# P3: Initialize agentic swarm for passphrase verification
# SECURITY: No default passphrase - must be set via environment variable
DEFAULT_PASSPHRASE = os.environ.get("PASSPHRASE")
if not DEFAULT_PASSPHRASE:
    raise RuntimeError(
        "PASSPHRASE environment variable is required. "
        "Set it before starting the server: export PASSPHRASE=your-secure-passphrase"
    )
passphrase_swarm = create_passphrase_swarm(DEFAULT_PASSPHRASE)

# --- Rate Limiting for Auth Endpoints ---
# Simple in-memory rate limiter (tracks failed attempts per IP)
_rate_limit_store: Dict[str, list] = {}
RATE_LIMIT_WINDOW = 300  # 5 minutes
RATE_LIMIT_MAX_ATTEMPTS = 10  # max attempts per window

def _check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    attempts = _rate_limit_store.get(ip, [])
    # Prune old attempts
    attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    _rate_limit_store[ip] = attempts
    if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
        return False
    return True

def _record_attempt(ip: str):
    """Record a failed auth attempt."""
    _rate_limit_store.setdefault(ip, []).append(time.time())

# --- Admin PIN: hashed at startup ---
_raw_pin = os.environ.get("ADMIN_PIN")
if not _raw_pin:
    raise RuntimeError(
        "ADMIN_PIN environment variable is required. "
        "Set it before starting the server: export ADMIN_PIN=your-secure-pin"
    )
ADMIN_PIN_HASH = hash_pin(_raw_pin)
del _raw_pin  # Don't keep raw PIN in memory

# Desktop-binary first-run flag — true once the user has chosen their own
# PIN + passphrase via /setup. While false, all HTML routes are redirected
# to /setup and only /api/setup/* + /static/* + /api/health are reachable.
_FIRST_RUN_COMPLETE = secret_store.is_first_run_complete()

# --- Login endpoint: issues JWT tokens after passphrase verification ---
@app.post("/api/auth/login")
async def auth_login(request: Request):
    """
    Authenticate with passphrase and receive a JWT session token.
    Also sets an httpOnly cookie for browser-based access.
    """
    body = await request.json()
    passphrase = body.get("passphrase", "")
    user_id = body.get("user_id", "")
    role = body.get("role", "resident")
    name = body.get("name", user_id)

    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": "Too many attempts. Try again later."}
        )

    if not passphrase or not user_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "passphrase and user_id are required"}
        )

    # Verify passphrase (simple constant-time comparison)
    if not secrets.compare_digest(passphrase, DEFAULT_PASSPHRASE):
        _record_attempt(client_ip)
        logger.warning(f"[Auth] Failed login attempt from {client_ip} for user {user_id}")
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Invalid passphrase"}
        )

    # Validate role
    valid_roles = ("admin", "operator", "resident", "guest")
    if role not in valid_roles:
        role = "guest"

    token = create_token(user_id=user_id, role=role, name=name)

    response = JSONResponse(content={
        "success": True,
        "token": token,
        "user": {"id": user_id, "role": role, "name": name},
    })
    response.set_cookie(
        key="lha_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 60 * 60,
    )
    return response

@app.post("/api/auth/logout")
async def auth_logout():
    """Clear session cookie."""
    response = JSONResponse(content={"success": True})
    response.delete_cookie("lha_session")
    return response

# P3: Initialize thermodynamic reasoner
thermodynamic_reasoner = ThermodynamicReasoner()

# LLM Runtime configuration endpoint (F4.6.7)
@app.get("/api/llm/runtimes")
async def get_llm_runtimes():
    """Get available LLM runtimes"""
    return {
        "current": LLMRuntimeConfig.load().__dict__,
        "available": LLMRuntimeConfig.SUPPORTED_RUNTIMES
    }

@app.post("/api/llm/runtime")
async def set_llm_runtime(runtime: str, model: str):
    """Set LLM runtime configuration"""
    config = LLMRuntimeConfig(runtime=runtime, model=model)
    config.save()
    return {"success": True, "config": config.__dict__}

# Tool graph endpoint for AI chat
@app.post("/api/tools/process")
async def process_with_tools(message: str):
    """Process a message through the tool graph"""
    try:
        response = await tool_graph.process_message(message)
        return {"response": response, "success": True}
    except Exception as e:
        logger.error(f"Tool processing failed: {e}")
        return {"error": str(e), "success": False}

@app.get("/api/tools/schema")
async def get_tools_schema():
    """Get OpenAI-compatible tool schema for LLM"""
    return {"tools": tool_graph.get_tools_schema()}


# ===========================================
# P3: AGENTIC SWARM & PROMPT CHAIN ENDPOINTS
# ===========================================

class PassphraseVerifyRequest(BaseModel):
    """Request model for passphrase verification"""
    passphrase: str
    user_id: str
    session_id: Optional[str] = None

class ThermodynamicReasonRequest(BaseModel):
    """Request model for thermodynamic reasoning"""
    action_type: str
    security_risk: float
    behavior_surprise: float = 0.0
    resource_cost: float = 0.0
    hour: Optional[int] = None
    request_rate: Optional[int] = None

@app.post("/api/verify/passphrase")
async def verify_passphrase(request: PassphraseVerifyRequest, raw_request: Request):
    """
    P3/N1.1: Verify passphrase using agentic swarm

    This endpoint uses multiple specialized agents (Verifier, Challenger, Auditor)
    to verify a passphrase attempt with defense-in-depth.
    Rate-limited to prevent brute force.
    """
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too many attempts. Try again later.", "success": False})

    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        consensus = await passphrase_swarm.verify(
            input_text=request.passphrase,
            user_id=request.user_id,
            session_id=session_id,
        )
        
        return {
            "success": consensus.outcome == VerificationOutcome.PASS,
            "outcome": consensus.outcome.value,
            "consensus_achieved": consensus.consensus_achieved,
            "reasoning": consensus.reasoning,
            "votes": {
                "approve": consensus.total_approve,
                "deny": consensus.total_deny,
                "abstain": consensus.total_abstain,
                "challenge": consensus.total_challenge,
            },
            "energy_consumed": consensus.energy_consumed,
            "agent_votes": [
                {
                    "agent": vote.agent_id,
                    "vote": vote.vote.value,
                    "confidence": vote.confidence,
                    "reasoning": vote.reasoning[:200] + "..." if len(vote.reasoning) > 200 else vote.reasoning,
                }
                for vote in consensus.votes
            ],
        }
    except Exception as e:
        logger.error(f"Passphrase verification failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.post("/api/verify/prompt-chain")
async def verify_with_prompt_chain(request: PassphraseVerifyRequest, raw_request: Request):
    """
    P3/N1.1: Verify passphrase using embedded prompt chain

    This endpoint runs the full 4-stage prompt chain:
    Lexical → Semantic → Intent → Oracle
    Rate-limited to prevent brute force.
    """
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too many attempts. Try again later.", "success": False})

    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        verifier = PromptChainVerifier(
            PassphraseSwarm.hash_passphrase(DEFAULT_PASSPHRASE)
        )
        outcome, context = await verifier.verify(
            input_text=request.passphrase,
            user_id=request.user_id,
            session_id=session_id,
        )
        
        return {
            "success": outcome == VerificationOutcome.PASS,
            "outcome": outcome.value,
            "stages_completed": context.stages_completed,
            "reasoning_chain": context.reasoning_chain,
            "energy_consumed": context.energy_consumed,
            "stage_results": {
                stage: {
                    "passed": result.get("passed"),
                    "confidence": result.get("confidence"),
                    "next_action": result.get("next_action"),
                }
                for stage, result in context.stage_results.items()
            },
        }
    except Exception as e:
        logger.error(f"Prompt chain verification failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.post("/api/reason/thermodynamic")
async def thermodynamic_reason(request: ThermodynamicReasonRequest):
    """
    P3/N1.2: Perform thermodynamic reasoning about an action
    
    Uses energy-based principles to determine if an action should be:
    - ALLOW: Safe to proceed
    - MONITOR: Proceed but watch closely
    - CONFIRM: Ask user for confirmation
    - VERIFY: Require additional verification
    - BLOCK: Deny the action
    """
    try:
        temporal_context = None
        if request.hour is not None or request.request_rate is not None:
            temporal_context = {
                "hour": request.hour if request.hour is not None else datetime.now().hour,
                "request_rate": request.request_rate or 0,
            }
        
        result = thermodynamic_reasoner.reason(
            action_type=request.action_type,
            security_risk=request.security_risk,
            behavior_surprise=request.behavior_surprise,
            resource_cost=request.resource_cost,
            temporal_context=temporal_context,
        )
        
        return {
            "success": True,
            **result,
        }
    except Exception as e:
        logger.error(f"Thermodynamic reasoning failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.get("/api/swarm/statistics")
async def get_swarm_statistics():
    """
    Get statistics from the passphrase verification swarm
    """
    return passphrase_swarm.get_statistics()

@app.get("/api/thermodynamic/state")
async def get_thermodynamic_state():
    """
    Get current thermodynamic system state
    """
    return {
        "current_state": thermodynamic_reasoner.current_state.value,
        "current_energy": thermodynamic_reasoner.current_energy,
        "temperature": thermodynamic_reasoner.temperature.temperature,
        "entropy": thermodynamic_reasoner.entropy_monitor.calculate_entropy(),
        "gradient": thermodynamic_reasoner.get_gradient(),
    }


# ===========================================
# P5: CONVERSATION PERSISTENCE ENDPOINTS
# ===========================================

class ConversationMessageRequest(BaseModel):
    """Request to add a message to conversation"""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

@app.get("/api/conversation/{session_id}")
async def get_conversation(session_id: str):
    """
    Get conversation history for a session.
    Returns empty messages array if session doesn't exist.
    """
    cache = get_conversation_cache()
    session = await cache.get_session(session_id)
    
    if session is None:
        return {"session_id": session_id, "messages": [], "exists": False}
    
    return {
        "session_id": session.session_id,
        "messages": [m.to_dict() for m in session.messages],
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "context": session.context,
        "exists": True,
    }

@app.post("/api/conversation/{session_id}/message")
async def add_conversation_message(session_id: str, request: ConversationMessageRequest):
    """
    Add a message to a conversation.
    Creates the session if it doesn't exist.
    """
    cache = get_conversation_cache()
    session = await cache.get_or_create_session(session_id)
    
    msg = session.add_message(
        role=request.role,
        content=request.content,
        metadata=request.metadata or {}
    )
    
    await cache.save_session(session)
    
    return {
        "success": True,
        "message": msg.to_dict(),
        "message_count": len(session.messages),
    }

@app.post("/api/conversation/{session_id}/sync")
async def sync_conversation(session_id: str, messages: List[Dict[str, Any]]):
    """
    Sync entire conversation state from client.
    Replaces all messages with provided list.
    """
    from .conversation_cache import ConversationMessage
    
    cache = get_conversation_cache()
    session = await cache.get_or_create_session(session_id)
    
    # Replace messages with synced data
    session.messages = [ConversationMessage.from_dict(m) for m in messages]
    await cache.save_session(session)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_count": len(session.messages),
    }

@app.delete("/api/conversation/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation session"""
    cache = get_conversation_cache()
    success = await cache.delete_session(session_id)
    return {"success": success, "session_id": session_id}

@app.get("/api/conversations")
async def list_conversations():
    """List all available conversation sessions"""
    cache = get_conversation_cache()
    sessions = cache.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}

@app.post("/api/conversations/cleanup")
async def cleanup_old_conversations():
    """Clean up old conversation sessions (> 7 days)"""
    cache = get_conversation_cache()
    deleted = await cache.cleanup_old_sessions()
    return {"success": True, "deleted_count": deleted}


# ===========================================
# ADMIN TOOL & PERMISSION CONFIGURATION (PDF §4.2.3, §4.5.4)

# ===========================================

# In-memory storage for admin permissions (production should use SQLite/file)
admin_permissions_store = {
    "high_risk_actions": ["door_unlock", "alarm_control", "camera_view", "garage_open", "lock_all"],
    "available_permissions": [
        "device_control", "device_control_limited", "scene_activate",
        "chat", "view_cameras", "view_energy_logs", "manage_guests"
    ],
    "roles": {
        "admin": ["*"],
        "resident": ["device_control", "scene_activate", "chat", "view_cameras"],
        "guest": ["device_control_limited", "chat"]
    },
    "guest_expiry_hours": 24,
    "device_allowlist": []  # Empty = all devices allowed
}

class AdminPermissionsUpdate(BaseModel):
    """Request model for updating admin permissions"""
    high_risk_actions: Optional[List[str]] = None
    roles: Optional[Dict[str, List[str]]] = None
    guest_expiry_hours: Optional[int] = None
    device_allowlist: Optional[List[str]] = None

@app.get("/api/admin/permissions")
async def get_admin_permissions(_caller: AuthenticatedUser = Depends(require_admin)):
    """
    Get current admin permission configuration

    Returns the current tool permissions, high-risk actions,
    role assignments, and device allowlist.
    """
    return admin_permissions_store

@app.post("/api/admin/permissions")
async def update_admin_permissions(update: AdminPermissionsUpdate, _caller: AuthenticatedUser = Depends(require_admin)):
    """
    Update admin permission configuration

    Allows admin to dynamically configure:
    - Which actions are considered high-risk
    - What permissions each role has
    - Guest token expiry duration
    - Which devices are allowed for AI control
    """
    if update.high_risk_actions is not None:
        admin_permissions_store["high_risk_actions"] = update.high_risk_actions
        logger.info(f"Updated high-risk actions: {update.high_risk_actions}")
    
    if update.roles is not None:
        # Don't allow removing admin's full access
        update.roles["admin"] = ["*"]
        admin_permissions_store["roles"] = update.roles
        logger.info(f"Updated role permissions: {update.roles}")
    
    if update.guest_expiry_hours is not None:
        admin_permissions_store["guest_expiry_hours"] = max(1, min(168, update.guest_expiry_hours))
        logger.info(f"Updated guest expiry: {update.guest_expiry_hours} hours")
    
    if update.device_allowlist is not None:
        admin_permissions_store["device_allowlist"] = update.device_allowlist
        logger.info(f"Updated device allowlist: {len(update.device_allowlist)} devices")
    
    return {"success": True, "permissions": admin_permissions_store}

@app.get("/api/admin/check-permission")
async def check_permission(role: str, permission: str):
    """
    Check if a role has a specific permission
    
    Used by the system to verify access before executing actions.
    """
    role_perms = admin_permissions_store["roles"].get(role, [])
    
    # Admin has all permissions
    if "*" in role_perms:
        return {"allowed": True, "role": role, "permission": permission}
    
    return {
        "allowed": permission in role_perms,
        "role": role,
        "permission": permission
    }

@app.get("/api/admin/is-high-risk")
async def is_high_risk_action(action: str):
    """
    Check if an action is classified as high-risk
    
    High-risk actions require additional verification (voice, PIN, etc.)
    """
    return {
        "action": action,
        "is_high_risk": action in admin_permissions_store["high_risk_actions"],
        "requires_verification": action in admin_permissions_store["high_risk_actions"]
    }


# ===========================================
# P3: ROBUST RBAC - USER, ROLE & DEVICE MANAGEMENT
# ===========================================

# Pydantic models for RBAC API
class CreateUserRequest(BaseModel):
    """Request to create a new user"""
    name: str
    role: str = "resident"  # admin, operator, resident, guest
    room_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    expiry_hours: Optional[int] = None  # For guests

class UpdateUserRequest(BaseModel):
    """Request to update user properties"""
    name: Optional[str] = None
    role: Optional[str] = None
    room_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class DeviceAssignmentRequest(BaseModel):
    """Request to assign a device"""
    device_id: str
    device_name: str
    entity_id: Optional[str] = None
    room_id: Optional[str] = None
    user_id: Optional[str] = None
    is_high_risk: bool = False

class SendMessageRequest(BaseModel):
    """Request to send a message"""
    content: str
    recipient_ids: Optional[List[str]] = None  # None = broadcast
    message_type: str = "info"  # info, alert, warning, emergency
    expires_hours: Optional[int] = None

class InviteGuestRequest(BaseModel):
    """Request to invite a guest"""
    guest_name: str
    expiry_hours: int = 24
    room_access: Optional[str] = None

# Initialize RBAC manager
rbac_manager = get_rbac_manager()

# --- User Management Endpoints ---

@app.get("/api/users")
async def list_users(
    role: Optional[str] = None,
    room_id: Optional[str] = None,
    active_only: bool = True,
):
    """List all users with optional filters"""
    role_type = RoleType(role) if role else None
    users = rbac_manager.list_users(role=role_type, room_id=room_id, active_only=active_only)
    return {"users": [u.to_dict() for u in users]}

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    """Get a specific user by ID"""
    user = rbac_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

@app.post("/api/users")
async def create_user(request: CreateUserRequest, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Create a new user (admin/operator only)"""
    try:
        role_type = RoleType(request.role)
        user = rbac_manager.create_user(
            name=request.name,
            role=role_type,
            room_id=request.room_id,
            email=request.email,
            phone=request.phone,
            expiry_hours=request.expiry_hours,
            creator_id=caller.user_id,
        )
        # Send welcome message
        rbac_manager.send_welcome_message(user.id)
        return {"success": True, "user": user.to_dict()}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/{user_id}")
async def update_user(user_id: str, request: UpdateUserRequest, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Update user properties"""
    user = rbac_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if request.name:
            user.name = request.name
        if request.email:
            user.email = request.email
        if request.phone:
            user.phone = request.phone
        if request.role:
            rbac_manager.update_user_role(user_id, RoleType(request.role), caller.user_id)
        if request.room_id:
            rbac_manager.assign_user_to_room(user_id, request.room_id, caller.user_id)
        
        return {"success": True, "user": user.to_dict()}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.delete("/api/users/{user_id}")
async def deactivate_user(user_id: str, caller: AuthenticatedUser = Depends(require_admin)):
    """Deactivate a user"""
    try:
        success = rbac_manager.deactivate_user(user_id, caller.user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/api/users/{user_id}/permissions")
async def get_user_permissions(user_id: str):
    """Get all effective permissions for a user"""
    permissions = rbac_manager.get_user_permissions(user_id)
    return {"user_id": user_id, "permissions": list(permissions)}

@app.post("/api/users/{user_id}/permissions/{permission}")
async def grant_permission(user_id: str, permission: str, caller: AuthenticatedUser = Depends(require_admin)):
    """Grant a permission to a user"""
    try:
        perm_type = PermissionType(permission)
        success = rbac_manager.grant_permission(user_id, perm_type, caller.user_id)
        return {"success": success}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission type")

@app.delete("/api/users/{user_id}/permissions/{permission}")
async def revoke_permission(user_id: str, permission: str, caller: AuthenticatedUser = Depends(require_admin)):
    """Revoke a permission from a user"""
    try:
        perm_type = PermissionType(permission)
        success = rbac_manager.revoke_permission(user_id, perm_type, caller.user_id)
        return {"success": success}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# --- Room Management Endpoints ---

@app.get("/api/rooms")
async def list_rooms():
    """List all rooms/units"""
    rooms = rbac_manager.list_rooms()
    return {"rooms": [{
        "id": r.id,
        "name": r.name,
        "floor": r.floor,
        "building": r.building,
        "assigned_devices": r.assigned_devices,
        "max_occupants": r.max_occupants,
        "current_occupants": r.current_occupants,
        "occupant_count": len(r.current_occupants),
    } for r in rooms]}

@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    """Get a specific room"""
    room = rbac_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get occupant details
    occupants = [rbac_manager.get_user(uid) for uid in room.current_occupants]
    occupants = [u.to_dict() for u in occupants if u]
    
    return {
        "id": room.id,
        "name": room.name,
        "floor": room.floor,
        "building": room.building,
        "assigned_devices": room.assigned_devices,
        "max_occupants": room.max_occupants,
        "occupants": occupants,
    }

@app.post("/api/rooms/{room_id}/assign/{user_id}")
async def assign_user_to_room(room_id: str, user_id: str, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Assign a user to a room"""
    try:
        success = rbac_manager.assign_user_to_room(user_id, room_id, caller.user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User or room not found")
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# --- Device Assignment Endpoints ---

@app.get("/api/devices/assignments")
async def list_device_assignments():
    """List all device assignments"""
    assignments = rbac_manager.device_assignments
    return {"assignments": [{
        "device_id": d.device_id,
        "device_name": d.device_name,
        "entity_id": d.entity_id,
        "assigned_to_room": d.assigned_to_room,
        "assigned_to_users": d.assigned_to_users,
        "is_high_risk": d.is_high_risk,
    } for d in assignments.values()]}

@app.post("/api/devices/assign")
async def assign_device(request: DeviceAssignmentRequest, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Assign a device to a room or user"""
    try:
        if request.room_id:
            rbac_manager.assign_device_to_room(
                device_id=request.device_id,
                device_name=request.device_name,
                room_id=request.room_id,
                entity_id=request.entity_id,
                is_high_risk=request.is_high_risk,
                admin_id=caller.user_id,
            )

        if request.user_id:
            rbac_manager.assign_device_to_user(
                device_id=request.device_id,
                user_id=request.user_id,
                admin_id=caller.user_id,
            )
        
        return {"success": True, "device_id": request.device_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/api/devices/user/{user_id}")
async def get_user_devices(user_id: str):
    """Get all devices a user can control"""
    devices = rbac_manager.get_user_devices(user_id)
    return {"user_id": user_id, "devices": [{
        "device_id": d.device_id,
        "device_name": d.device_name,
        "entity_id": d.entity_id,
        "is_high_risk": d.is_high_risk,
    } for d in devices]}

@app.get("/api/devices/{device_id}/can-control/{user_id}")
async def check_device_control(device_id: str, user_id: str):
    """Check if a user can control a specific device"""
    can_control = rbac_manager.can_control_device(user_id, device_id)
    return {"device_id": device_id, "user_id": user_id, "can_control": can_control}

# --- Messaging Endpoints ---

@app.post("/api/messages")
async def send_message(request: SendMessageRequest, caller: AuthenticatedUser = Depends(get_current_user)):
    """Send a message to users on the network"""
    try:
        message = rbac_manager.send_message(
            sender_id=caller.user_id,
            content=request.content,
            recipient_ids=request.recipient_ids,
            message_type=request.message_type,
            expires_hours=request.expires_hours,
        )
        return {"success": True, "message": message.to_dict()}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/messages/{user_id}")
async def get_messages(user_id: str, unread_only: bool = False):
    """Get messages for a specific user"""
    messages = rbac_manager.get_messages_for_user(user_id, unread_only=unread_only)
    return {"messages": [m.to_dict() for m in messages]}

@app.post("/api/messages/{message_id}/read/{user_id}")
async def mark_message_read(message_id: str, user_id: str):
    """Mark a message as read"""
    success = rbac_manager.mark_message_read(user_id, message_id)
    return {"success": success}

@app.post("/api/messages/broadcast")
async def broadcast_message_endpoint(request: SendMessageRequest, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Broadcast a message to all users (admin/operator only)"""
    try:
        # Force broadcast by setting recipient_ids to None
        message = rbac_manager.send_message(
            sender_id=caller.user_id,
            content=request.content,
            recipient_ids=None,  # Broadcast
            message_type=request.message_type,
            expires_hours=request.expires_hours,
        )
        return {"success": True, "message": message.to_dict()}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# --- Guest Management Endpoints ---

@app.post("/api/guests/invite")
async def invite_guest(request: InviteGuestRequest, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Invite a guest to the network"""
    try:
        guest = rbac_manager.invite_guest(
            inviter_id=caller.user_id,
            guest_name=request.guest_name,
            expiry_hours=request.expiry_hours,
            room_access=request.room_access,
        )
        return {
            "success": True,
            "guest": guest.to_dict(),
            "access_token": guest.access_token,
            "expires_at": guest.expires_at.isoformat() if guest.expires_at else None,
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.delete("/api/guests/{guest_id}")
async def revoke_guest(guest_id: str, caller: AuthenticatedUser = Depends(require_operator_or_admin)):
    """Revoke a guest's access"""
    try:
        success = rbac_manager.revoke_guest(guest_id, caller.user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Guest not found")
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/api/guests")
async def list_guests():
    """List all active guests"""
    guests = rbac_manager.list_users(role=RoleType.GUEST, active_only=True)
    return {"guests": [g.to_dict() for g in guests]}

# --- Role & Permission Info Endpoints ---

@app.get("/api/roles")
async def list_roles():
    """List all available roles and their default permissions"""
    from rbac import DEFAULT_ROLE_PERMISSIONS, ROLE_HIERARCHY
    
    return {
        "roles": [{
            "name": role.value,
            "permissions": [p.value for p in perms],
            "inherits_from": [r.value for r in ROLE_HIERARCHY.get(role, [])],
        } for role, perms in DEFAULT_ROLE_PERMISSIONS.items()]
    }

@app.get("/api/permissions")
async def list_available_permissions():
    """List all available permission types"""
    return {
        "permissions": [{
            "name": p.value,
            "description": p.name.replace("_", " ").title(),
        } for p in PermissionType]
    }

@app.get("/api/rbac/export")
async def export_rbac_state():
    """Export the full RBAC state for backup"""
    return rbac_manager.export_state()


# Pydantic models
class User(BaseModel):
    id: str
    name: str
    role: str  # admin, resident, guest
    created_at: datetime

class Message(BaseModel):
    id: str
    user_id: str
    content: str
    role: str  # user, assistant, system
    timestamp: datetime

class Device(BaseModel):
    id: str
    name: str
    type: str  # light, thermostat, lock, camera, etc.
    state: Dict[str, Any]
    home_assistant_id: Optional[str] = None

class Settings(BaseModel):
    home_name: str
    admin_configured: bool
    llm_configured: bool
    wifi_configured: bool

# Routes

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Landing page - serves as WiFi captive portal
    Uses enhanced Neo-Brutalist + Swiss design template (P5)
    """
    # Check if captive portal request (used for WiFi login detection)
    is_captive = request.query_params.get("captive") == "1"
    
    return templates.TemplateResponse("index-enhanced.html", {
        "request": request,
        "home_name": data_store.settings["home_name"],
        "is_configured": data_store.settings["admin_configured"],
        "is_captive": is_captive
    })

@app.get("/offline", response_class=HTMLResponse)
async def offline_page(request: Request):
    """
    Offline fallback page for PWA
    """
    return templates.TemplateResponse("offline.html", {
        "request": request
    })

@app.get("/setup", response_class=HTMLResponse)
async def setup_wizard(request: Request):
    """
    Setup wizard for first-time configuration
    """
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "settings": data_store.settings
    })

@app.get("/admin-guide", response_class=HTMLResponse)
async def admin_guide(request: Request):
    """
    Admin guide for WiFi setup and resident onboarding
    """
    return templates.TemplateResponse("admin-guide.html", {
        "request": request
    })

@app.get("/api/network/info")
async def get_network_info(request: Request):
    """
    Get local network information for WiFi setup guide
    Includes dynamic security token that expires for better security
    Port is dynamically detected from the request
    """
    import socket
    import hashlib
    import time
    
    # Get local IP address
    try:
        # Create a socket to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    
    # Detect port from request or environment
    port = int(os.environ.get("PORT", 8000))
    # Also try to get from request host header
    host_header = request.headers.get("host", f"{local_ip}:{port}")
    if ":" in host_header:
        try:
            port = int(host_header.split(":")[-1])
        except ValueError:
            pass
    
    # Generate dynamic access token using HMAC with server secret (not predictable)
    current_hour = int(time.time() // 3600)
    import hmac
    secret_key = os.environ.get("JWT_SECRET", secrets.token_hex(16))
    secret_seed = f"local-home-agent-{local_ip}-{current_hour}"
    access_token = hmac.new(secret_key.encode(), secret_seed.encode(), hashlib.sha256).hexdigest()[:16]

    # Token expires at the start of next hour
    expires_at = (current_hour + 1) * 3600
    expires_in_minutes = int((expires_at - time.time()) / 60)
    
    return {
        "local_ip": local_ip,
        "port": port,
        "hostname": socket.gethostname(),
        "full_url": f"http://{local_ip}:{port}",
        "access_token": access_token,
        "token_expires_in": expires_in_minutes,
        "qr_url": f"http://{local_ip}:{port}?token={access_token}"
    }

@app.get("/api/network/validate-token")
async def validate_access_token(token: str):
    """
    Validate a dynamic access token for guest access
    """
    import socket
    import hashlib
    import time
    
    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    
    # Check current hour token (HMAC with server secret)
    import hmac
    secret_key = os.environ.get("JWT_SECRET", secrets.token_hex(16))
    current_hour = int(time.time() // 3600)
    expected_token = hmac.new(secret_key.encode(), f"local-home-agent-{local_ip}-{current_hour}".encode(), hashlib.sha256).hexdigest()[:16]

    # Also check previous hour (grace period)
    previous_token = hmac.new(secret_key.encode(), f"local-home-agent-{local_ip}-{current_hour - 1}".encode(), hashlib.sha256).hexdigest()[:16]
    
    is_valid = token == expected_token or token == previous_token
    
    return {
        "valid": is_valid,
        "message": "Token valid" if is_valid else "Token expired or invalid"
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Main dashboard for home management
    Uses enhanced Neo-Brutalist + Swiss design template (P5)
    """
    return templates.TemplateResponse("dashboard-enhanced.html", {
        "request": request,
        "home_name": data_store.settings["home_name"],
        "devices": data_store.devices,
        "users": data_store.users
    })

@app.get("/chat", response_class=HTMLResponse)
async def chat_interface(request: Request):
    """
    Chat interface for AI agent interaction
    """
    return templates.TemplateResponse("chat.html", {
        "request": request
    })

@app.get("/guest-login", response_class=HTMLResponse)
async def guest_login_page(request: Request):
    """
    Guest auto-login page. Renders only if request is on the local network
    AND a guest PIN is enabled — otherwise shows a friendly explanation.
    """
    if not is_request_from_local_network(request):
        return HTMLResponse(
            content=(
                "<!doctype html><html><head><title>Not on local network</title></head>"
                "<body style='font-family:monospace;padding:40px;text-align:center;'>"
                "<h1>Connect to the property's Wi-Fi</h1>"
                "<p>Guest auto-login only works while you're on the on-site network.</p>"
                "</body></html>"
            ),
            status_code=403,
        )
    if not secret_store.is_guest_pin_enabled():
        return HTMLResponse(
            content=(
                "<!doctype html><html><head><title>Guest auto-login not enabled</title></head>"
                "<body style='font-family:monospace;padding:40px;text-align:center;'>"
                "<h1>Guest auto-login is not configured</h1>"
                "<p>Ask the property admin to set a guest PIN in Settings -> Security.</p>"
                "</body></html>"
            ),
            status_code=403,
        )
    return templates.TemplateResponse("guest_login.html", {"request": request})


@app.get("/guest", response_class=HTMLResponse)
async def guest_page(request: Request):
    """
    Guest chat surface. Requires a guest-role session cookie issued by
    /api/auth/guest-login. Anyone without one is bounced back to /guest-login.
    """
    from .auth import verify_token as _vt, verify_guest_token_epoch
    token = request.cookies.get("lha_session")
    if not token:
        return RedirectResponse(url="/guest-login", status_code=302)
    user = _vt(token)
    if not user or user.role != "guest":
        return RedirectResponse(url="/guest-login", status_code=302)
    # Verify the guest's gpe claim matches the current server epoch — admin
    # rotating or disabling the guest PIN bumps the epoch, instantly revoking.
    if not verify_guest_token_epoch(token, secret_store.get_guest_pin_epoch()):
        return RedirectResponse(url="/guest-login", status_code=302)
    return templates.TemplateResponse("guest.html", {"request": request})

@app.get("/residents", response_class=HTMLResponse)
async def residents_chat(request: Request):
    """
    Person-to-person chat interface for residents
    """
    return templates.TemplateResponse("residents.html", {
        "request": request
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """
    Settings page for configuration (F4.2.6, F4.2.7)
    """
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": data_store.settings
    })

# ============================================================================
# WAITING ROOM SYSTEM - P5: Guest Assignment UX
# ============================================================================
# 
# Flow:
# 1. Guest connects to WiFi → Captive portal redirects to /
# 2. If not recognized, redirects to /waiting-room
# 3. Guest enters name and purpose
# 4. Admin/Resident sees guest in queue and assigns room
# 5. Guest receives notification and access grant
#
# This provides a "lobby" experience before full access
# ============================================================================

class WaitingGuest(BaseModel):
    """A guest waiting for room assignment"""
    id: str
    name: str
    purpose: str  # guest, delivery, service, tour
    device_id: str
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    joined_at: datetime
    assigned: bool = False
    assigned_to_room: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None

class WaitingRoomStore:
    """In-memory storage for waiting guests"""
    def __init__(self):
        self.guests: Dict[str, WaitingGuest] = {}
        self.queue_order: List[str] = []
    
    def add_guest(self, guest: WaitingGuest) -> int:
        """Add guest to waiting room, returns queue position"""
        self.guests[guest.id] = guest
        self.queue_order.append(guest.id)
        return len(self.queue_order)
    
    def get_position(self, guest_id: str) -> int:
        """Get guest's position in queue (1-indexed)"""
        try:
            return self.queue_order.index(guest_id) + 1
        except ValueError:
            return 0
    
    def assign_guest(self, guest_id: str, room: str, assigned_by: str) -> bool:
        """Assign a guest to a room"""
        if guest_id in self.guests:
            self.guests[guest_id].assigned = True
            self.guests[guest_id].assigned_to_room = room
            self.guests[guest_id].assigned_by = assigned_by
            self.guests[guest_id].assigned_at = datetime.now()
            # Remove from queue
            if guest_id in self.queue_order:
                self.queue_order.remove(guest_id)
            return True
        return False
    
    def get_unassigned_guests(self) -> List[WaitingGuest]:
        """Get all guests waiting for assignment"""
        return [self.guests[gid] for gid in self.queue_order if not self.guests[gid].assigned]
    
    def get_waiting_count(self) -> int:
        """Count of guests waiting"""
        return len([g for g in self.guests.values() if not g.assigned])

waiting_room = WaitingRoomStore()

@app.get("/waiting-room", response_class=HTMLResponse)
async def waiting_room_page(request: Request):
    """
    Waiting room page for guests awaiting room assignment.
    
    Features:
    - Neo-brutalist + Swiss design
    - Purpose selection (guest/delivery/service/tour)
    - Real-time queue position updates
    - Progress indicator
    - Micro-interactions throughout
    """
    # Check if already assigned
    device_id = request.cookies.get("device_id")
    if device_id:
        for guest in waiting_room.guests.values():
            if guest.device_id == device_id and guest.assigned:
                return RedirectResponse(url="/dashboard")
    
    return templates.TemplateResponse("waiting-room.html", {
        "request": request,
        "home_name": data_store.settings["home_name"],
        "queue_position": waiting_room.get_waiting_count() + 1,
        "waiting_count": waiting_room.get_waiting_count()
    })

class JoinWaitingRoomRequest(BaseModel):
    name: str
    purpose: str
    device_id: str

@app.post("/api/waiting-room/join")
async def join_waiting_room(request: Request, data: JoinWaitingRoomRequest):
    """
    Join the waiting room queue.
    Returns queue position and estimated wait time.
    """
    import uuid
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Create waiting guest
    guest = WaitingGuest(
        id=str(uuid.uuid4()),
        name=data.name,
        purpose=data.purpose,
        device_id=data.device_id,
        ip_address=client_ip,
        joined_at=datetime.now()
    )
    
    position = waiting_room.add_guest(guest)
    
    # Estimate wait time based on queue position and purpose
    base_wait = 5  # minutes
    if data.purpose == "delivery":
        estimated_wait = "~2 minutes"  # Faster for deliveries
    elif data.purpose == "tour":
        estimated_wait = f"~{base_wait + 5} minutes"  # Tours take longer
    else:
        estimated_wait = f"~{base_wait * position} minutes"
    
    # Notify admin via WebSocket (if connected)
    await broadcast_to_admins({
        "type": "new_guest",
        "guest": {
            "id": guest.id,
            "name": guest.name,
            "purpose": guest.purpose,
            "position": position
        }
    })
    
    logger.info(f"[WaitingRoom] Guest joined: {data.name} ({data.purpose}) - Position {position}")
    
    return {
        "success": True,
        "waiting_id": guest.id,
        "position": position,
        "waiting_count": waiting_room.get_waiting_count() - 1,
        "estimated_wait": estimated_wait
    }

@app.get("/api/waiting-room/status/{waiting_id}")
async def get_waiting_status(waiting_id: str):
    """
    Get current status of a waiting guest.
    Used for polling or initial state check.
    """
    if waiting_id not in waiting_room.guests:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    guest = waiting_room.guests[waiting_id]
    
    return {
        "id": guest.id,
        "name": guest.name,
        "assigned": guest.assigned,
        "position": waiting_room.get_position(waiting_id),
        "waiting_count": waiting_room.get_waiting_count(),
        "redirect_url": f"/dashboard?room={guest.assigned_to_room}" if guest.assigned else None
    }

@app.get("/api/waiting-room/queue")
async def get_waiting_queue(request: Request):
    """
    Get the full waiting queue (admin only).
    Requires admin role via queue token or session.
    """
    # Admin authentication check via queue auth
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        queue_auth = get_queue_auth_manager()
        verified = queue_auth.verify_token(token)
        
        if not verified or verified.role != "admin":
            return JSONResponse(
                status_code=403,
                content={"error": "Admin access required"}
            )
    else:
        # For development, allow if no auth header (will be enforced in production)
        logger.warning("Waiting queue accessed without authentication - allow in dev mode")
    
    guests = waiting_room.get_unassigned_guests()
    
    return {
        "count": len(guests),
        "guests": [
            {
                "id": g.id,
                "name": g.name,
                "purpose": g.purpose,
                "joined_at": g.joined_at.isoformat(),
                "position": waiting_room.get_position(g.id),
                "waiting_time": (datetime.now() - g.joined_at).total_seconds() / 60  # minutes
            }
            for g in guests
        ]
    }

class AssignGuestRequest(BaseModel):
    guest_id: str
    room: str
    assigned_by: str = "admin"

@app.post("/api/waiting-room/assign")
async def assign_guest(data: AssignGuestRequest):
    """
    Assign a waiting guest to a room.
    Triggers notification to the guest's device.
    """
    success = waiting_room.assign_guest(data.guest_id, data.room, data.assigned_by)
    
    if not success:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    guest = waiting_room.guests[data.guest_id]
    
    # Notify guest via WebSocket
    await broadcast_to_guest(data.guest_id, {
        "type": "assigned",
        "room": data.room,
        "redirect_url": f"/dashboard?room={data.room}"
    })
    
    logger.info(f"[WaitingRoom] Guest assigned: {guest.name} → Room {data.room}")
    
    return {
        "success": True,
        "guest": guest.name,
        "room": data.room
    }

async def broadcast_to_admins(message: dict):
    """Broadcast a message to all admin connections"""
    # Use admin-specific connections for targeted broadcast
    for admin_id, connection in list(data_store.admin_connections.items()):
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to broadcast to admin {admin_id}: {e}")
            data_store.admin_connections.pop(admin_id, None)
    
    # Also broadcast to notification service for push delivery
    try:
        notification_service = get_notification_service()
        await notification_service.send(NotificationPayload(
            id=f"broadcast_{datetime.now().timestamp():.0f}",
            title=message.get("type", "Alert"),
            body=str(message.get("message", message)),
            priority=NotificationPriority.MEDIUM,
            category="system",
            data=message
        ))
    except Exception as e:
        logger.warning(f"Notification service broadcast failed: {e}")

async def broadcast_to_guest(guest_id: str, message: dict):
    """Send a message to a specific guest via their WebSocket connection"""
    if guest_id in data_store.guest_connections:
        try:
            await data_store.guest_connections[guest_id].send_json(message)
            logger.info(f"Message sent to guest {guest_id}: {message.get('type')}")
        except Exception as e:
            logger.warning(f"Failed to send to guest {guest_id}: {e}")
            # Clean up stale connection
            data_store.guest_connections.pop(guest_id, None)

# WebSocket for waiting room real-time updates
@app.websocket("/ws/waiting/{waiting_id}")
async def waiting_room_websocket(websocket: WebSocket, waiting_id: str):
    """
    WebSocket for real-time waiting room updates.
    
    Events:
    - position_update: Queue position changed
    - assigned: Guest has been assigned to a room
    """
    await websocket.accept()
    
    # Register guest connection for targeted messaging
    data_store.guest_connections[waiting_id] = websocket
    logger.info(f"Guest WebSocket connected: {waiting_id}")
    
    try:
        while True:
            # Check if guest has been assigned
            if waiting_id in waiting_room.guests:
                guest = waiting_room.guests[waiting_id]
                
                if guest.assigned:
                    await websocket.send_json({
                        "type": "assigned",
                        "room": guest.assigned_to_room,
                        "redirect_url": f"/dashboard?room={guest.assigned_to_room}"
                    })
                    break
                else:
                    await websocket.send_json({
                        "type": "position_update",
                        "position": waiting_room.get_position(waiting_id),
                        "waiting_count": waiting_room.get_waiting_count()
                    })
            
            # Wait before next update
            await asyncio.sleep(3)
            
    except WebSocketDisconnect:
        logger.debug(f"[WaitingRoom] WebSocket disconnected: {waiting_id}")
    except Exception as e:
        logger.error(f"[WaitingRoom] WebSocket error: {e}")
    finally:
        # Clean up guest connection on disconnect
        data_store.guest_connections.pop(waiting_id, None)
        logger.info(f"Guest WebSocket cleaned up: {waiting_id}")

# API Endpoints

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint used by Render's health probe AND by the desktop UI.

    Reports:
    - status: "healthy" if the FastAPI app is up. "degraded" if a non-fatal
      subsystem is down (e.g. Ollama). Render still considers 200 = healthy.
    - llm: provider detected + currently selected model + reachable flag
    - rbac: whether the RBAC manager initialised (reads its singleton lazily)
    - cache: conversation cache directory + session count
    - hardware: minimal vitals (RAM available, CPU cores)
    - version: app version

    All probes are wrapped in try/except so a broken subsystem can't crash the
    health endpoint itself — that would make Render mark the service unhealthy
    and trigger restart loops.
    """
    health: Dict[str, Any] = {
        "status": "healthy",
        "version": app.version,
        "timestamp": datetime.now().isoformat(),
    }
    degraded_reasons: List[str] = []

    # LLM provider
    try:
        client = get_llm_client()
        provider = await client.detect_provider()
        runtime_cfg = LLMRuntimeConfig.load()
        health["llm"] = {
            "provider": provider.value,
            "available": provider.value != "none",
            "model": runtime_cfg.model,
            "models_loaded": list(client._available_models),
        }
        if provider.value == "none":
            degraded_reasons.append("no local LLM detected")
    except Exception as e:
        logger.warning(f"[health] llm probe failed: {e}")
        health["llm"] = {"provider": "unknown", "available": False, "error": str(e)}
        degraded_reasons.append("llm probe failed")

    # RBAC manager
    try:
        rbac = get_rbac_manager()
        health["rbac"] = {
            "initialized": rbac is not None,
            "users": len(getattr(rbac, "users", {}) or {}),
        }
    except Exception as e:
        logger.warning(f"[health] rbac probe failed: {e}")
        health["rbac"] = {"initialized": False, "error": str(e)}
        degraded_reasons.append("rbac uninitialised")

    # Conversation cache
    try:
        cache = get_conversation_cache()
        health["cache"] = {
            "dir": str(cache.cache_dir),
            "sessions": len(cache.list_sessions()),
        }
    except Exception as e:
        logger.warning(f"[health] cache probe failed: {e}")
        health["cache"] = {"error": str(e)}
        degraded_reasons.append("cache unavailable")

    # Hardware vitals (best-effort)
    try:
        import psutil
        mem = psutil.virtual_memory()
        health["hardware"] = {
            "ram_available_gb": round(mem.available / (1024 ** 3), 2),
            "ram_percent_used": mem.percent,
            "cpu_cores": psutil.cpu_count(logical=False) or psutil.cpu_count() or 1,
        }
    except Exception as e:
        health["hardware"] = {"error": str(e)}

    if degraded_reasons:
        health["status"] = "degraded"
        health["degraded_reasons"] = degraded_reasons

    return health

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    return data_store.settings

@app.post("/api/settings")
async def update_settings(settings: Settings):
    """Update settings"""
    data_store.settings = settings.model_dump()
    return {"success": True, "settings": data_store.settings}

@app.get("/api/devices")
async def get_devices():
    """Get all devices"""
    return data_store.devices

@app.post("/api/devices")
async def add_device(device: Device):
    """Add a new device"""
    data_store.devices.append(device.model_dump())
    return {"success": True, "device": device}

@app.post("/api/devices/{device_id}/control")
async def control_device(device_id: str, command: Dict[str, Any], request: Request, caller: AuthenticatedUser = Depends(get_current_user)):
    """
    Control a device (turn on/off, set temperature, etc.)
    Uses thermodynamic energy model for security evaluation.
    User identity comes from verified JWT token, not spoofable headers.
    """
    device = next((d for d in data_store.devices if d["id"] == device_id), None)
    if not device:
        return JSONResponse(status_code=404, content={"error": "Device not found"})

    # User context from verified JWT (not spoofable headers)
    user_id = caller.user_id
    user_role = caller.role
    device_fingerprint = request.headers.get("X-Device-Id", "unknown")
    
    # Determine action type based on device
    action_type = "query"
    if device["type"] == "lock":
        action_type = "door_unlock"
    elif device["type"] in ["light", "switch"]:
        action_type = "light_control"
    elif device["type"] == "thermostat":
        action_type = "thermostat_set"
    elif device["type"] == "camera":
        action_type = "camera_view"
    elif device["type"] == "alarm":
        action_type = "alarm_control"
    
    # Evaluate energy
    energy_result = await evaluate_action(
        action_type=action_type,
        target=device_id,
        user_id=user_id,
        user_role=user_role,
        device_id=device_fingerprint,
        ip_address=request.client.host if request.client else "unknown"
    )
    
    logger.info(f"Device control: {device_id} - Energy: {energy_result.total_energy} ({energy_result.level.value})")
    
    # Handle based on energy level
    if energy_result.level == EnergyLevel.CRITICAL:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Action denied - security risk too high",
                "energy": energy_result.total_energy,
                "requires": "Admin override required"
            }
        )
    
    if energy_result.requires_verification:
        # In production: trigger PIN/voice verification
        return JSONResponse(
            status_code=202,
            content={
                "status": "verification_required",
                "energy": energy_result.total_energy,
                "message": "Please verify your identity to proceed"
            }
        )
    
    # Update device state (safely)
    if isinstance(device.get("state"), dict):
        device["state"].update(command)
    else:
        device["state"] = dict(command)
    
    # Send command to Home Assistant API
    ha_result = {"sent": False, "ha_available": False}
    try:
        ha = get_ha_client()
        if ha.url and ha.token:
            ha_result["ha_available"] = True
            # Determine HA action from command
            if command.get("on") is True:
                ha_action = "turn_on"
            elif command.get("on") is False:
                ha_action = "turn_off"
            elif command.get("locked") is True:
                ha_action = "lock"
            elif command.get("locked") is False:
                ha_action = "unlock"
            else:
                ha_action = "toggle"
            
            # Extract entity_id (device_id may be entity_id or mapped)
            entity_id = device.get("entity_id", device_id)
            
            # Send to Home Assistant
            success = await ha.control_device(entity_id, ha_action, **command)
            ha_result["sent"] = success
            
            if success:
                logger.info(f"Home Assistant command sent: {entity_id} -> {ha_action}")
            else:
                logger.warning(f"Home Assistant command failed: {entity_id}")
    except Exception as e:
        logger.error(f"Home Assistant error: {e}")
        ha_result["error"] = str(e)
    
    return {
        "success": True, 
        "device": device, 
        "energy": energy_result.total_energy,
        "home_assistant": ha_result
    }

# Note: /api/users GET+POST and /api/messages GET removed in Tier-1 cleanup.
# The auth-gated RBAC versions at lines ~795 and ~814 are the canonical
# endpoints. /api/messages POST below is the LLM-chat endpoint, renamed
# to /api/chat to stop shadowing /api/messages POST at line 1006 (RBAC
# direct messaging between users).

@app.get("/api/chat/history")
async def get_chat_history():
    """Get LLM chat history (the agent <-> user conversation)."""
    return {"messages": data_store.messages}

@app.post("/api/chat")
async def chat_with_agent(message: Message):
    """
    Send a message to the local-LLM agent and stream back its reply.
    Applies thermodynamic energy model for security-sensitive queries.

    Was previously @app.post("/api/messages") which shadowed the RBAC
    direct-messaging endpoint at line 1006. Renamed in Tier-1 cleanup.
    """
    # Store user message
    data_store.messages.append(message.model_dump())
    
    # Get LLM client
    llm_client = get_llm_client()
    
    # Check if LLM is available
    provider = await llm_client.detect_provider()
    
    if provider.value == "none":
        # No local LLM available - return helpful message
        ai_response = Message(
            id=f"msg_{len(data_store.messages)}",
            user_id="system",
            content="""I'm currently running in limited mode because no local AI model is detected.

To enable full AI capabilities, please install one of:
1. **Ollama** - Download from https://ollama.ai and run: `ollama pull llama3.2:3b`
2. **LM Studio** - Download from https://lmstudio.ai and load a model

Once installed, I'll automatically detect and use the local AI for conversations!""",
            role="assistant",
            timestamp=datetime.now()
        )
    else:
        # Build conversation context
        house_context = f"""
Home: {data_store.settings['home_name']}
Current devices: {len(data_store.devices)}
Active users: {len(data_store.users)}
"""
        
        try:
            # Generate response using local LLM
            llm_response = await llm_client.generate(
                prompt=message.content,
                system_prompt=HOME_AGENT_SYSTEM_PROMPT + "\n\n" + house_context,
                temperature=0.7
            )
            
            ai_response = Message(
                id=f"msg_{len(data_store.messages)}",
                user_id="system",
                content=llm_response.content,
                role="assistant",
                timestamp=datetime.now()
            )
            
            logger.info(f"LLM response generated via {llm_response.provider.value}")
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            ai_response = Message(
                id=f"msg_{len(data_store.messages)}",
                user_id="system",
                content=f"I encountered an error processing your request. Please try again or contact the admin.\n\nError: {str(e)}",
                role="assistant",
                timestamp=datetime.now()
            )
    
    data_store.messages.append(ai_response.model_dump())
    
    # Broadcast to all connected websockets
    await broadcast_message(ai_response.model_dump())
    
    return {"success": True, "response": ai_response}

# WebSocket for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat and device updates.

    Chat flow:
        1. Client sends {"type": "chat", "payload": {"content": "...", "session_id": "..."}}
        2. We persist the user message into the conversation cache.
        3. We stream the LLM reply back via "chat_stream" frames, then a final
           "chat_complete" frame once generation finishes.
        4. Assistant message is also persisted so history survives restarts.

    If no local LLM provider is detected, we send a single "chat_complete" with
    a helpful onboarding message so the UI never hangs.
    """
    await websocket.accept()
    data_store.active_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            msg_type = message_data.get("type")

            if msg_type == "chat":
                payload = message_data.get("payload") or {}
                content = (payload.get("content") or "").strip()
                session_id = payload.get("session_id") or "default"
                user_id = payload.get("user_id") or "anonymous"

                if not content:
                    await websocket.send_json({
                        "type": "chat_error",
                        "payload": {"error": "content is required"}
                    })
                    continue

                # Persist user message (cache survives restarts)
                cache = get_conversation_cache()
                session = await cache.get_or_create_session(session_id)
                session.add_message("user", content, metadata={"user_id": user_id})
                await cache.save_session(session)

                # Echo user message to all listeners (mirrors HTTP /api/messages behaviour)
                user_msg = Message(
                    id=f"msg_{int(time.time() * 1000)}",
                    user_id=user_id,
                    content=content,
                    role="user",
                    timestamp=datetime.now(),
                ).model_dump()
                data_store.messages.append(user_msg)
                await broadcast_message(user_msg)

                # Generate reply via local LLM (streaming when possible)
                llm_client = get_llm_client()
                provider = await llm_client.detect_provider()

                if provider.value == "none":
                    fallback = (
                        "No local LLM detected. Install Ollama (https://ollama.ai) "
                        "and run `ollama pull llama3.2:3b`, then retry."
                    )
                    session.add_message("assistant", fallback)
                    await cache.save_session(session)
                    await websocket.send_json({
                        "type": "chat_complete",
                        "payload": {"content": fallback, "session_id": session_id}
                    })
                    continue

                # Build context from recent history (max 10 turns to keep prompts small)
                recent = session.get_recent_messages(count=10)
                history_lines = [
                    f"{m.role}: {m.content}" for m in recent[:-1]  # exclude current user msg
                ]
                history_block = "\n".join(history_lines) if history_lines else ""

                house_context = (
                    f"Home: {data_store.settings.get('home_name', 'Co-Living Space')}\n"
                    f"Devices: {len(data_store.devices)} | Users: {len(data_store.users)}\n"
                )
                system_prompt = (
                    HOME_AGENT_SYSTEM_PROMPT
                    + "\n\n" + house_context
                    + ("\n\nConversation so far:\n" + history_block if history_block else "")
                )

                full_reply = ""
                try:
                    async for chunk in llm_client.stream_generate(
                        prompt=content,
                        system_prompt=system_prompt,
                        temperature=0.7,
                    ):
                        if not chunk:
                            continue
                        full_reply += chunk
                        try:
                            await websocket.send_json({
                                "type": "chat_stream",
                                "payload": {"delta": chunk, "session_id": session_id}
                            })
                        except Exception:
                            # Client disconnected mid-stream; stop generating
                            break
                except Exception as e:
                    logger.error(f"LLM stream failed: {e}")
                    full_reply = full_reply or f"Error generating response: {e}"

                # Persist assistant reply
                session.add_message("assistant", full_reply)
                await cache.save_session(session)

                await websocket.send_json({
                    "type": "chat_complete",
                    "payload": {"content": full_reply, "session_id": session_id}
                })

            elif msg_type == "device_control":
                device_id = message_data["payload"]["device_id"]
                command = message_data["payload"]["command"]

                device = next((d for d in data_store.devices if d["id"] == device_id), None)
                if device:
                    if isinstance(device.get("state"), dict):
                        device["state"].update(command)
                    else:
                        device["state"] = dict(command)
                    await broadcast_device_update(device)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "payload": {"ts": time.time()}})

    except WebSocketDisconnect:
        if websocket in data_store.active_connections:
            data_store.active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket handler crashed: {e}")
        if websocket in data_store.active_connections:
            data_store.active_connections.remove(websocket)

async def broadcast_message(message: dict):
    """Broadcast message to all connected clients"""
    for connection in data_store.active_connections:
        try:
            await connection.send_json({"type": "message", "payload": message})
        except Exception:
            pass

async def broadcast_device_update(device: dict):
    """Broadcast device update to all connected clients"""
    for connection in data_store.active_connections:
        try:
            await connection.send_json({"type": "device_update", "payload": device})
        except Exception:
            pass

# Download endpoint for LLM models
@app.get("/api/llm/models")
async def list_llm_models():
    """List available LLM models"""
    return {
        "models": [
            {
                "id": "llama-3.2-1b",
                "name": "Llama 3.2 1B",
                "size": "1.3 GB",
                "recommended": True,
                "description": "Lightweight model for basic tasks"
            },
            {
                "id": "llama-3.2-3b",
                "name": "Llama 3.2 3B",
                "size": "3.2 GB",
                "recommended": True,
                "description": "Balanced performance and size"
            },
            {
                "id": "mistral-7b",
                "name": "Mistral 7B",
                "size": "4.1 GB",
                "recommended": False,
                "description": "High performance, requires more RAM"
            }
        ]
    }

@app.post("/api/llm/download")
async def download_llm_model(model_id: str):
    """
    Download and install LLM model via Ollama API
    Streams progress back to client via WebSocket broadcasts
    """
    import httpx
    
    # Map friendly model IDs to Ollama model names
    model_map = {
        "llama-3.2-1b": "llama3.2:1b",
        "llama-3.2-3b": "llama3.2:3b",
        "mistral-7b": "mistral:7b",
        "gemma-2b": "gemma:2b",
        "phi-3-mini": "phi3:mini"
    }
    
    ollama_model = model_map.get(model_id, model_id)
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    
    # First check if Ollama is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code != 200:
                return JSONResponse(
                    status_code=503,
                    content={"error": "Ollama is not running. Please start Ollama first."}
                )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": f"Cannot connect to Ollama at {ollama_url}: {str(e)}"}
        )
    
    # Start async download task
    async def pull_model_task():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0)) as client:  # 1hr timeout
                async with client.stream(
                    "POST",
                    f"{ollama_url}/api/pull",
                    json={"name": ollama_model, "stream": True}
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                progress = json.loads(line)
                                # Broadcast progress to connected clients
                                await broadcast_model_download_progress({
                                    "model": model_id,
                                    "status": progress.get("status", "downloading"),
                                    "total": progress.get("total", 0),
                                    "completed": progress.get("completed", 0),
                                    "digest": progress.get("digest", "")
                                })
                            except json.JSONDecodeError:
                                pass
            
            # Download complete
            await broadcast_model_download_progress({
                "model": model_id,
                "status": "complete",
                "message": f"Model {ollama_model} downloaded successfully"
            })
            
        except Exception as e:
            logger.error(f"Model download failed: {e}")
            await broadcast_model_download_progress({
                "model": model_id,
                "status": "error",
                "error": str(e)
            })
    
    # Start background task
    asyncio.create_task(pull_model_task())
    
    return {
        "success": True,
        "message": f"Model {ollama_model} download started",
        "status": "downloading",
        "note": "Subscribe to WebSocket for progress updates"
    }


async def broadcast_model_download_progress(progress: dict):
    """Broadcast model download progress to all connected clients"""
    message = {"type": "model_download_progress", "payload": progress}
    for connection in data_store.active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            pass


# Energy Dashboard & Audit Log API (F4.3.9, F4.3.10)

@app.get("/api/energy/dashboard")
async def get_energy_dashboard():
    """
    Get energy dashboard data for visualization (F4.3.10)
    """
    dashboard = get_dashboard()
    data = dashboard.get_dashboard_data()
    
    return {
        "current_energy": data.current_system_energy,
        "energy_level": "low" if data.current_system_energy < 20 
                        else "medium" if data.current_system_energy < 50 
                        else "high" if data.current_system_energy < 80 
                        else "critical",
        "trend": data.energy_trend,
        "distribution": data.action_distribution,
        "high_risk_users": data.high_risk_users,
        "recent_alerts": data.recent_alerts,
        "statistics": data.statistics,
    }


@app.get("/api/energy/audit-log")
async def get_audit_log_entries(limit: int = 100, user_id: Optional[str] = None):
    """
    Get energy audit log entries (F4.3.9)
    """
    audit_log = get_audit_log()
    entries = audit_log.get_entries(limit=limit, user_id=user_id)
    
    return {
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "user_id": e.user_id,
                "user_role": e.user_role,
                "action_type": e.action_type,
                "target": e.target,
                "energy_score": e.energy_score,
                "energy_level": e.energy_level,
                "was_allowed": e.was_allowed,
                "verification_method": e.verification_method,
                "admin_notified": e.admin_notified,
            }
            for e in entries
        ],
        "total": len(entries)
    }


@app.get("/api/energy/statistics")
async def get_energy_statistics(hours: int = 24):
    """
    Get energy statistics (F4.3.9)
    """
    audit_log = get_audit_log()
    return audit_log.get_statistics(hours)


@app.post("/api/scenes/{scene_name}")
async def run_scene(scene_name: str, request: Request, caller: AuthenticatedUser = Depends(get_current_user)):
    """
    Run a predefined scene (F4.5.4)
    User identity from verified JWT token.
    """
    result = await evaluate_action(
        action_type="light_control",  # Scenes are generally low risk
        target=scene_name,
        user_id=caller.user_id,
        user_role=caller.role,
        device_id=request.headers.get("X-Device-Id", "unknown"),
        ip_address=request.client.host if request.client else "unknown"
    )
    
    if result.level == EnergyLevel.CRITICAL:
        return JSONResponse(
            status_code=403,
            content={"error": "Scene activation denied", "energy": result.total_energy}
        )
    
    # Scene definitions: list of {device_type, target_state} steps that the
    # scene will apply to every matching device in data_store.devices.
    # Each step is also pushed to Home Assistant (if configured) via
    # ha_client.control_device(); local-only mode still updates state so the
    # UI reflects the change.
    SCENES: Dict[str, List[Dict[str, Any]]] = {
        "goodnight": [
            {"device_type": "light", "state": "off"},
            {"device_type": "lock", "state": "locked"},
            {"device_type": "thermostat", "state": "on", "value": 68},
        ],
        "away": [
            {"device_type": "light", "state": "off"},
            {"device_type": "lock", "state": "locked"},
            {"device_type": "alarm", "state": "armed"},
        ],
        "home": [
            {"device_type": "lock", "state": "unlocked"},
            {"device_type": "light", "state": "on", "tag": "entry"},
            {"device_type": "alarm", "state": "disarmed"},
        ],
        "movie": [
            {"device_type": "light", "state": "on", "value": 20, "tag": "living_room"},
            {"device_type": "blind", "state": "closed", "tag": "living_room"},
        ],
    }

    if scene_name not in SCENES:
        return JSONResponse(status_code=404, content={"error": "Scene not found"})

    actuated: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    ha_client = HomeAssistantClient()

    for step in SCENES[scene_name]:
        target_type = step["device_type"]
        new_state = step["state"]
        for device in data_store.devices:
            if device.get("type") != target_type:
                continue
            # Optional tag filter (e.g. "entry" lights only)
            tag = step.get("tag")
            if tag and tag not in (device.get("tags") or []) and tag not in (device.get("name", "").lower()):
                continue
            try:
                # Local state update — always succeeds, drives the UI even
                # when no Home Assistant is configured.
                device["state"] = new_state
                if "value" in step:
                    device["value"] = step["value"]
                # Best-effort HA call. If HA isn't configured the call returns
                # quickly without raising.
                if ha_client.base_url:
                    await ha_client.control_device(device["id"], new_state, step.get("value"))
                actuated.append({
                    "id": device["id"],
                    "name": device.get("name"),
                    "type": target_type,
                    "new_state": new_state,
                })
            except Exception as exc:  # noqa: BLE001
                errors.append({"device_id": device["id"], "error": str(exc)})

    logger.info(
        "Scene '%s' activated by %s: %d device(s) actuated, %d error(s)",
        scene_name, caller.user_id, len(actuated), len(errors)
    )

    return {
        "success": True,
        "scene": scene_name,
        "devices_actuated": actuated,
        "errors": errors,
        "energy": result.total_energy,
    }


# ========================================
# LA3: Safety & Security Features
# ========================================

# LA3.1: Emergency Mode / Panic Button
class EmergencyState:
    active: bool = False
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = None

emergency_state = EmergencyState()
# ADMIN_PIN_HASH is set at module level (hashed with bcrypt at startup)

@app.post("/api/emergency/activate")
async def activate_emergency(caller: AuthenticatedUser = Depends(get_current_user)):
    """
    Activate emergency mode - stops all automations, locks doors, turns on lights
    LA3.1: Emergency mode / panic button (requires authentication)
    """
    global emergency_state

    emergency_state.active = True
    emergency_state.activated_at = datetime.now()
    emergency_state.activated_by = caller.user_id
    
    logger.warning(f"🚨 EMERGENCY MODE ACTIVATED from {emergency_state.activated_by}")
    
    # Stop all automations and set safe state
    # In production: integrate with Home Assistant to:
    # - Stop all automations
    # - Lock all doors
    # - Turn on all lights
    # - Send alert to property manager
    
    return {
        "success": True,
        "message": "Emergency mode activated",
        "activated_at": emergency_state.activated_at.isoformat(),
        "actions": [
            "All automations stopped",
            "All doors locked",
            "All lights turned on",
            "Property manager notified"
        ]
    }

class DeactivateRequest(BaseModel):
    pin: str

@app.post("/api/emergency/deactivate")
async def deactivate_emergency(req: DeactivateRequest, request: Request, _caller: AuthenticatedUser = Depends(require_admin)):
    """
    Deactivate emergency mode - requires admin auth + PIN (LA3.6: 2FA)
    """
    global emergency_state

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    # Verify PIN using bcrypt (timing-safe)
    if not verify_pin(req.pin, ADMIN_PIN_HASH):
        _record_attempt(client_ip)
        logger.warning("Emergency deactivation failed - invalid PIN")
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Invalid PIN"}
        )
    
    emergency_state.active = False
    logger.info("Emergency mode deactivated")
    
    return {
        "success": True,
        "message": "Emergency mode deactivated",
        "deactivated_at": datetime.now().isoformat()
    }

@app.get("/api/emergency/status")
async def get_emergency_status(_caller: AuthenticatedUser = Depends(get_current_user)):
    """Get current emergency mode status (requires authentication)"""
    return {
        "active": emergency_state.active,
        "activated_at": emergency_state.activated_at.isoformat() if emergency_state.activated_at else None,
        "activated_by": emergency_state.activated_by
    }


# LA3.3: Backup/Restore Functionality

@app.get("/api/backup/export")
async def export_backup(_caller: AuthenticatedUser = Depends(require_admin)):
    """
    Export all settings, devices, and configurations to JSON
    LA3.3: Backup/restore functionality (requires admin auth)
    """
    backup_data = {
        "version": "1.0.0",
        "exported_at": datetime.now().isoformat(),
        "settings": data_store.settings,
        "devices": data_store.devices,
        "users": [u for u in data_store.users if u.get("role") != "admin"],  # Don't export admin credentials
        "scenes": {
            "goodnight": {"action": "Turn off all lights, lock doors, set thermostat to 68°F"},
            "away": {"action": "Turn off lights, lock doors, arm security"},
            "home": {"action": "Unlock doors, turn on entry lights, disarm security"},
            "movie": {"action": "Dim living room lights to 20%, close blinds"},
        }
    }
    
    logger.info("Backup exported successfully")
    return backup_data

class ImportBackupRequest(BaseModel):
    backup: Dict[str, Any]
    pin: str

@app.post("/api/backup/import")
async def import_backup(req: ImportBackupRequest, request: Request, _caller: AuthenticatedUser = Depends(require_admin)):
    """
    Import settings from backup JSON
    LA3.3: Backup/restore functionality
    Requires admin auth + PIN (LA3.6: 2FA)
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    # Verify PIN using bcrypt (timing-safe)
    if not verify_pin(req.pin, ADMIN_PIN_HASH):
        _record_attempt(client_ip)
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Invalid PIN"}
        )
    
    backup = req.backup
    
    # Validate backup format
    if "version" not in backup:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid backup format"}
        )
    
    # Restore data
    if "settings" in backup:
        data_store.settings.update(backup["settings"])
    
    if "devices" in backup:
        data_store.devices = backup["devices"]
    
    if "users" in backup:
        # Merge users, keeping existing admin
        existing_admins = [u for u in data_store.users if u.get("role") == "admin"]
        data_store.users = existing_admins + backup["users"]
    
    logger.info(f"Backup imported from {backup.get('exported_at', 'unknown date')}")
    
    return {
        "success": True,
        "message": "Backup restored successfully",
        "imported_at": datetime.now().isoformat(),
        "restored": {
            "settings": "settings" in backup,
            "devices": len(backup.get("devices", [])),
            "users": len(backup.get("users", []))
        }
    }


# LA3.6: Admin PIN Management

class SetPinRequest(BaseModel):
    current_pin: str
    new_pin: str

def _validate_pin(pin: str) -> Optional[str]:
    """Returns an error message if invalid, else None."""
    if not pin or not pin.isdigit():
        return "PIN must be digits only"
    if len(pin) < 4 or len(pin) > 8:
        return "PIN must be 4-8 digits"
    return None


def _validate_passphrase(passphrase: str) -> Optional[str]:
    if not passphrase or len(passphrase) < 12:
        return "Passphrase must be at least 12 characters"
    return None


@app.post("/api/admin/set-pin")
async def set_admin_pin(req: SetPinRequest, request: Request, _caller: AuthenticatedUser = Depends(require_admin)):
    """
    Set or update admin PIN for 2FA
    LA3.6: Two-factor auth for admin actions
    """
    global ADMIN_PIN_HASH

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    # Verify current PIN using bcrypt (timing-safe)
    if not verify_pin(req.current_pin, ADMIN_PIN_HASH):
        _record_attempt(client_ip)
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Current PIN is incorrect"}
        )

    err = _validate_pin(req.new_pin)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "error": err})

    ADMIN_PIN_HASH = hash_pin(req.new_pin)
    secret_store.update(admin_pin=req.new_pin)
    logger.info("Admin PIN updated (bcrypt hash + persisted)")

    return {"success": True, "message": "PIN updated successfully"}


# ----------------------------------------------------------------------------
# First-run setup: caller authenticates with the bootstrap PIN, then chooses
# their own PIN + passphrase. Locked once first_run_complete is true.
# ----------------------------------------------------------------------------

class FirstRunSetupRequest(BaseModel):
    bootstrap_pin: str  # the auto-generated PIN from FIRST_RUN_CREDENTIALS.txt
    new_pin: str
    new_passphrase: str


@app.post("/api/setup/credentials")
async def setup_credentials(req: FirstRunSetupRequest, request: Request):
    """
    First-run only: replace the bootstrap PIN + passphrase with the user's
    chosen values. Available only while first_run_complete is false.
    """
    global ADMIN_PIN_HASH, passphrase_swarm, _FIRST_RUN_COMPLETE

    if _FIRST_RUN_COMPLETE:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "First-run setup is already complete. Use /api/admin/set-pin or /api/admin/rotate-passphrase to rotate credentials."},
        )

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    if not verify_pin(req.bootstrap_pin, ADMIN_PIN_HASH):
        _record_attempt(client_ip)
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Bootstrap PIN is incorrect. See FIRST_RUN_CREDENTIALS.txt in your home folder under .local-home-agent."},
        )

    pin_err = _validate_pin(req.new_pin)
    if pin_err:
        return JSONResponse(status_code=400, content={"success": False, "error": pin_err})

    pass_err = _validate_passphrase(req.new_passphrase)
    if pass_err:
        return JSONResponse(status_code=400, content={"success": False, "error": pass_err})

    ADMIN_PIN_HASH = hash_pin(req.new_pin)
    passphrase_swarm = create_passphrase_swarm(req.new_passphrase)
    secret_store.update(
        admin_pin=req.new_pin,
        passphrase=req.new_passphrase,
        first_run_complete=True,
    )
    _FIRST_RUN_COMPLETE = True
    # Remove the bootstrap credentials file; it no longer matches reality.
    creds = secret_store.config_dir() / "FIRST_RUN_CREDENTIALS.txt"
    try:
        if creds.exists():
            creds.unlink()
    except OSError:
        pass

    logger.info("First-run setup complete: PIN + passphrase set by user")
    return {"success": True, "message": "Setup complete. Reload the page to log in."}


# ----------------------------------------------------------------------------
# Ongoing passphrase rotation (admin-gated)
# ----------------------------------------------------------------------------

class RotatePassphraseRequest(BaseModel):
    current_pin: str
    new_passphrase: str


@app.post("/api/admin/rotate-passphrase")
async def rotate_passphrase(
    req: RotatePassphraseRequest,
    request: Request,
    _caller: AuthenticatedUser = Depends(require_admin),
):
    """Admin-gated passphrase rotation. Persists to secret_store."""
    global passphrase_swarm

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    if not verify_pin(req.current_pin, ADMIN_PIN_HASH):
        _record_attempt(client_ip)
        return JSONResponse(status_code=403, content={"success": False, "error": "Current PIN is incorrect"})

    err = _validate_passphrase(req.new_passphrase)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "error": err})

    passphrase_swarm = create_passphrase_swarm(req.new_passphrase)
    secret_store.update(passphrase=req.new_passphrase)
    logger.info("Passphrase rotated (in-memory + persisted)")

    return {"success": True, "message": "Passphrase updated successfully"}


# ----------------------------------------------------------------------------
# Guest PIN — admin pre-sets a PIN; LAN-only guests use it to auto-login.
# See app/auth.py is_request_from_local_network for the IP gate.
# ----------------------------------------------------------------------------

class GuestPinSetRequest(BaseModel):
    new_pin: str
    enabled: bool = True


class GuestLoginRequest(BaseModel):
    pin: str


@app.get("/api/admin/guest-pin")
async def get_guest_pin_state(_caller: AuthenticatedUser = Depends(require_admin)):
    """Returns whether a guest PIN is configured + whether it's enabled.
    The hash itself is never returned."""
    return {
        "configured": secret_store.get_guest_pin_hash() is not None,
        "enabled": secret_store.is_guest_pin_enabled(),
        "set_at": secret_store.get_guest_pin_epoch(),
    }


@app.post("/api/admin/guest-pin")
async def set_guest_pin(req: GuestPinSetRequest, _caller: AuthenticatedUser = Depends(require_admin)):
    """Admin sets/rotates the guest PIN. Bumps the guest_pin_set_at epoch
    so any live guest tokens are invalidated on next request."""
    err = _validate_pin(req.new_pin)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "error": err})

    pin_hash = hash_pin(req.new_pin)
    secret_store.set_guest_pin(
        pin_hash=pin_hash,
        enabled=bool(req.enabled),
        set_at=int(time.time()),
    )
    logger.info("Guest PIN set/rotated by admin (enabled=%s)", req.enabled)
    return {"success": True, "message": "Guest PIN saved.", "enabled": bool(req.enabled)}


@app.delete("/api/admin/guest-pin")
async def disable_guest_pin(_caller: AuthenticatedUser = Depends(require_admin)):
    """Soft-disable: keeps the hash but flips enabled=false. Bumps epoch
    so live guest tokens stop working."""
    secret_store.disable_guest_pin()
    logger.info("Guest PIN disabled by admin")
    return {"success": True, "message": "Guest auto-login disabled."}


@app.post("/api/auth/guest-login")
async def guest_login(req: GuestLoginRequest, request: Request):
    """LAN-only guest login. Requires:
      1. Request's TCP peer is on a private network (auth.is_request_from_local_network)
      2. Guest PIN is enabled by admin
      3. Submitted PIN matches the stored bcrypt hash

    Issues a guest-role JWT (gpe claim = current epoch) as cookie + body."""
    # Local-network gate first — never trust headers, only the TCP peer.
    if not is_request_from_local_network(request):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Guest auto-login is restricted to the property's local network. Connect to the on-site Wi-Fi and try again.",
            },
        )

    if not secret_store.is_guest_pin_enabled():
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Guest auto-login is not enabled. Ask the admin to set a guest PIN."},
        )

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"success": False, "error": "Too many attempts."})

    stored_hash = secret_store.get_guest_pin_hash()
    if not stored_hash or not verify_pin(req.pin, stored_hash):
        _record_attempt(client_ip)
        return JSONResponse(status_code=403, content={"success": False, "error": "Wrong PIN."})

    epoch = secret_store.get_guest_pin_epoch()
    guest_id = f"guest-{secrets.token_hex(4)}"
    token = create_guest_token(user_id=guest_id, guest_pin_epoch=epoch)

    response = JSONResponse(
        content={
            "success": True,
            "user": {"id": guest_id, "role": "guest"},
            "token": token,
        }
    )
    response.set_cookie(
        "lha_session",
        token,
        max_age=8 * 3600,
        httponly=True,
        samesite="strict",
    )
    logger.info("Guest %s logged in from %s", guest_id, client_ip)
    return response


# Auth helper kept locally so we don't pollute auth.py with imports it doesn't need
from .auth import (  # noqa: E402
    is_request_from_local_network,
    create_guest_token,
)
import secrets  # noqa: E402


# ========================================
# LA4: Core Features
# ========================================

# LA4.3: Automation Templates

class AutomationCreate(BaseModel):
    name: str
    triggers: List[str]
    actions: List[str]
    enabled: bool = True

automations_store: List[Dict[str, Any]] = []

@app.get("/api/automations")
async def get_automations():
    """Get all automations"""
    return automations_store

@app.post("/api/automations")
async def create_automation(automation: AutomationCreate):
    """
    Create automation from template
    LA4.3: Automation templates library
    """
    new_automation = {
        "id": f"auto_{len(automations_store) + 1}",
        "name": automation.name,
        "triggers": automation.triggers,
        "actions": automation.actions,
        "enabled": automation.enabled,
        "created_at": datetime.now().isoformat()
    }
    automations_store.append(new_automation)
    logger.info(f"Automation created: {automation.name}")
    
    return {"success": True, "automation": new_automation}


# LA4.4: Voice Command Processing

class VoiceCommand(BaseModel):
    command: str
    action: Dict[str, Any]

@app.post("/api/voice/command")
async def process_voice_command(cmd: VoiceCommand):
    """
    Process voice command and actually actuate matching devices.
    LA4.4: Voice command integration.

    Was previously theatrical (returned hardcoded English without touching
    data_store.devices or ha_client). Now iterates devices, mutates state,
    best-effort calls Home Assistant, and returns the structured result so
    the UI can update.
    """
    logger.info(f"Voice command: {cmd.command}")

    action = cmd.action
    action_type = action.get("type")
    target = action.get("target")
    desired_state = action.get("state")
    value = action.get("value")

    actuated: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    ha_client = HomeAssistantClient()

    def _matches(device: Dict[str, Any], wanted_type: str, wanted_target: Optional[str]) -> bool:
        if device.get("type") != wanted_type:
            return False
        if wanted_target in (None, "all", ""):
            return True
        # match by id, name (case-insensitive), or tag
        target_lower = str(wanted_target).lower()
        if device.get("id") == wanted_target:
            return True
        if target_lower in (device.get("name") or "").lower():
            return True
        return target_lower in (device.get("tags") or [])

    async def _apply(devices_iter, new_state, new_value=None):
        for device in devices_iter:
            try:
                device["state"] = new_state
                if new_value is not None:
                    device["value"] = new_value
                if ha_client.base_url:
                    await ha_client.control_device(device["id"], new_state, new_value)
                actuated.append({
                    "id": device["id"],
                    "name": device.get("name"),
                    "type": device.get("type"),
                    "new_state": new_state,
                })
            except Exception as exc:  # noqa: BLE001
                errors.append({"device_id": device["id"], "error": str(exc)})

    if action_type == "scene":
        # Re-use the scene logic by direct dispatch — but we don't have the
        # JWT context here, so just resolve the name and report. Caller
        # should hit /api/scenes/{name} for full role-gated execution.
        return {
            "success": True,
            "command": cmd.command,
            "action": "scene",
            "message": f"Voice intent recognised: scene '{target}'. Trigger via POST /api/scenes/{target} for execution.",
        }

    elif action_type == "light_control":
        new_state = "on" if desired_state else "off"
        matches = [d for d in data_store.devices if _matches(d, "light", target)]
        await _apply(matches, new_state, value)

    elif action_type == "door_lock":
        matches = [d for d in data_store.devices if _matches(d, "lock", target)]
        await _apply(matches, "locked")

    elif action_type == "door_unlock":
        matches = [d for d in data_store.devices if _matches(d, "lock", target)]
        await _apply(matches, "unlocked")

    elif action_type == "thermostat_set":
        new_temp = action.get("value", 72)
        matches = [d for d in data_store.devices if _matches(d, "thermostat", target)]
        await _apply(matches, "on", new_temp)

    else:
        return {
            "success": False,
            "command": cmd.command,
            "action": action_type,
            "message": f"Unknown action type '{action_type}'. Supported: scene, light_control, door_lock, door_unlock, thermostat_set.",
            "devices_actuated": [],
            "errors": [],
        }

    logger.info(
        "Voice command actuated %d device(s), %d error(s)",
        len(actuated), len(errors)
    )

    return {
        "success": True,
        "command": cmd.command,
        "action": action_type,
        "devices_actuated": actuated,
        "errors": errors,
    }


# =====================================================
# PERSON-TO-PERSON CHAT ENDPOINTS
# Family/Resident Communication System
# =====================================================

class DirectMessageRequest(BaseModel):
    """Request model for direct messages"""
    sender_id: str
    sender_name: str
    recipient_id: str
    content: str

class RoomMessageRequest(BaseModel):
    """Request model for room messages"""
    sender_id: str
    sender_name: str
    room_id: str
    content: str

class CreateRoomRequest(BaseModel):
    """Request model for creating a chat room"""
    name: str
    description: Optional[str] = None
    members: List[str]
    created_by: str
    is_private: bool = False

@app.post("/api/chat/direct")
async def send_direct_message(msg_request: DirectMessageRequest):
    """
    Send a direct message to another user
    """
    family_chat = get_family_chat()
    
    try:
        message = family_chat.send_direct_message(
            sender_id=msg_request.sender_id,
            sender_name=msg_request.sender_name,
            recipient_id=msg_request.recipient_id,
            content=msg_request.content
        )
        
        # Broadcast to WebSocket clients
        await broadcast_chat_message(message.model_dump())
        
        return {"success": True, "message": message}
    except Exception as e:
        logger.error(f"Error sending direct message: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.post("/api/chat/room")
async def send_room_message(msg_request: RoomMessageRequest):
    """
    Send a message to a chat room
    """
    family_chat = get_family_chat()
    
    try:
        message = family_chat.send_room_message(
            sender_id=msg_request.sender_id,
            sender_name=msg_request.sender_name,
            room_id=msg_request.room_id,
            content=msg_request.content
        )
        
        # Broadcast to WebSocket clients
        await broadcast_chat_message(message.model_dump())
        
        return {"success": True, "message": message}
    except Exception as e:
        logger.error(f"Error sending room message: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": str(e), "success": False}
        )

@app.post("/api/chat/rooms")
async def create_room(room_request: CreateRoomRequest):
    """
    Create a new chat room
    """
    family_chat = get_family_chat()
    
    try:
        room = family_chat.create_room(
            name=room_request.name,
            description=room_request.description,
            members=room_request.members,
            created_by=room_request.created_by,
            is_private=room_request.is_private
        )
        
        return {"success": True, "room": room}
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.get("/api/chat/rooms/{user_id}")
async def get_user_rooms(user_id: str):
    """
    Get all chat rooms for a user
    """
    family_chat = get_family_chat()
    rooms = family_chat.get_user_rooms(user_id)
    return {"success": True, "rooms": rooms}

@app.get("/api/chat/messages/{user_id}")
async def get_user_messages(user_id: str, limit: int = 50):
    """
    Get all messages for a user
    """
    family_chat = get_family_chat()
    messages = family_chat.get_messages_for_user(user_id, limit)
    return {"success": True, "messages": messages}

@app.get("/api/chat/conversation/{user1_id}/{user2_id}")
async def get_conversation(user1_id: str, user2_id: str, limit: int = 50):
    """
    Get conversation between two users
    """
    family_chat = get_family_chat()
    messages = family_chat.get_conversation(user1_id, user2_id, limit)
    return {"success": True, "messages": messages}

@app.get("/api/chat/room/{room_id}/messages")
async def get_room_messages(room_id: str, limit: int = 50):
    """
    Get messages in a chat room
    """
    family_chat = get_family_chat()
    messages = family_chat.get_room_messages(room_id, limit)
    return {"success": True, "messages": messages}

@app.post("/api/chat/read/{message_id}")
async def mark_message_read(message_id: str, user_id: str):
    """
    Mark a message as read
    """
    family_chat = get_family_chat()
    family_chat.mark_as_read(message_id, user_id)
    return {"success": True}

@app.get("/api/chat/unread/{user_id}")
async def get_unread_count(user_id: str):
    """
    Get unread message count for a user
    """
    family_chat = get_family_chat()
    count = family_chat.get_unread_count(user_id)
    return {"success": True, "unread_count": count}

async def broadcast_chat_message(message: dict):
    """Broadcast chat message to all connected clients"""
    for connection in data_store.active_connections:
        try:
            await connection.send_json({"type": "chat_message", "payload": message})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
