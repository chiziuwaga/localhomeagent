"""
Platform pairing — links this LHA instance to a user account on the
Co-Living platform (coliving.fixitforme.ai).

Flow:
  1. User runs the agent for the first time. POST /api/pair/init returns a
     one-time 8-character code with a 10-minute TTL plus the agent's stable
     agent_id (a UUID persisted to ~/.local-home-agent/agent_id).
  2. User pastes the code (and the agent's reachable URL) into the Co-Living
     Settings → Local Home Agent panel.
  3. Co-Living calls POST /api/pair/confirm on the agent with the code +
     their user_open_id. The agent validates the code, persists the pairing
     to disk, and returns the agent_id.
  4. From that point on, both sides know about each other; the agent stores
     the user's openId and the optional callback URL.

Distinct from `iot_pairing_wizard.py` which onboards smart-home devices INTO
the agent. This module is the AGENT ↔ PLATFORM handshake.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".local-home-agent"
PAIRING_FILE = CONFIG_DIR / "pairing.json"
AGENT_ID_FILE = CONFIG_DIR / "agent_id"

CODE_TTL_SECONDS = 600  # 10 minutes
CODE_LENGTH_BYTES = 4  # 8 hex characters

# Single in-memory active code; one pending pair at a time per agent.
_active_code: Optional[dict] = None


class PairInitResponse(BaseModel):
    code: str = Field(..., description="One-time 8-character pairing code (uppercase hex).")
    expires_at: float = Field(..., description="Unix timestamp when the code expires.")
    agent_id: str = Field(..., description="Stable identifier for this agent instance.")


class PairConfirmRequest(BaseModel):
    code: str
    user_open_id: str
    user_email: Optional[str] = None
    callback_url: Optional[str] = None


class PairConfirmResponse(BaseModel):
    success: bool
    agent_id: str
    message: str


class PairStatusResponse(BaseModel):
    paired: bool
    agent_id: str
    user_open_id: Optional[str] = None
    user_email: Optional[str] = None
    paired_at: Optional[float] = None


def _get_or_create_agent_id() -> str:
    """Return the persistent agent_id, creating it on first call."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if AGENT_ID_FILE.exists():
        return AGENT_ID_FILE.read_text().strip()
    new_id = secrets.token_hex(16)
    AGENT_ID_FILE.write_text(new_id)
    return new_id


def _save_pairing(
    user_open_id: str,
    user_email: Optional[str],
    callback_url: Optional[str],
) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PAIRING_FILE.write_text(
        json.dumps(
            {
                "user_open_id": user_open_id,
                "user_email": user_email,
                "callback_url": callback_url,
                "paired_at": time.time(),
            }
        )
    )


def get_current_pairing() -> Optional[dict]:
    """Read the persisted pairing, or None if the agent isn't paired yet."""
    if not PAIRING_FILE.exists():
        return None
    try:
        return json.loads(PAIRING_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def reset_active_code_for_tests() -> None:
    """Test-only helper to clear the in-memory pending code."""
    global _active_code
    _active_code = None


def create_platform_pairing_routes() -> APIRouter:
    router = APIRouter(prefix="/api/pair", tags=["platform-pairing"])

    @router.post("/init", response_model=PairInitResponse)
    async def init_pairing() -> PairInitResponse:
        """Generate a one-time pairing code. Existing pairings remain valid
        until /confirm is called with a fresh, valid code."""
        global _active_code
        code = secrets.token_hex(CODE_LENGTH_BYTES).upper()
        expires_at = time.time() + CODE_TTL_SECONDS
        _active_code = {"code": code, "expires_at": expires_at}
        return PairInitResponse(
            code=code,
            expires_at=expires_at,
            agent_id=_get_or_create_agent_id(),
        )

    @router.post("/confirm", response_model=PairConfirmResponse)
    async def confirm_pairing(req: PairConfirmRequest) -> PairConfirmResponse:
        global _active_code
        if not _active_code:
            raise HTTPException(status_code=400, detail="No pairing in progress")
        if time.time() > _active_code["expires_at"]:
            _active_code = None
            raise HTTPException(status_code=400, detail="Pairing code expired")
        if req.code.upper() != _active_code["code"]:
            raise HTTPException(status_code=400, detail="Invalid pairing code")
        _save_pairing(req.user_open_id, req.user_email, req.callback_url)
        agent_id = _get_or_create_agent_id()
        _active_code = None
        return PairConfirmResponse(
            success=True,
            agent_id=agent_id,
            message=f"Paired with user {req.user_open_id}",
        )

    @router.get("/status", response_model=PairStatusResponse)
    async def pairing_status() -> PairStatusResponse:
        pairing = get_current_pairing()
        return PairStatusResponse(
            paired=pairing is not None,
            agent_id=_get_or_create_agent_id(),
            user_open_id=pairing.get("user_open_id") if pairing else None,
            user_email=pairing.get("user_email") if pairing else None,
            paired_at=pairing.get("paired_at") if pairing else None,
        )

    @router.post("/unpair")
    async def unpair() -> dict:
        if PAIRING_FILE.exists():
            PAIRING_FILE.unlink()
        return {"success": True}

    return router
