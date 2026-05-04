"""
Authentication & Authorization Middleware for Local Home Agent

Provides JWT-based authentication using FastAPI's dependency injection.
Replaces the old pattern of default `admin_id="admin-001"` query parameters
and spoofable X-User-Id / X-User-Role headers.

Usage:
    from .auth import require_admin, require_resident, get_current_user, AuthenticatedUser

    @app.post("/api/protected")
    async def my_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
        print(user.user_id, user.role)

    @app.post("/api/admin-only")
    async def admin_endpoint(user: AuthenticatedUser = Depends(require_admin)):
        ...
"""

import os
import time
import logging
from typing import Optional
from dataclasses import dataclass

import jwt
import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# JWT configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 8 * 60 * 60  # 8 hours

if not JWT_SECRET:
    # Generate a random secret for development (not persisted across restarts)
    import secrets
    JWT_SECRET = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET not set — using randomly generated secret. "
        "Sessions will not survive server restarts. "
        "Set JWT_SECRET environment variable for production."
    )

# Optional bearer token (also accept from cookie)
_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Represents a verified user extracted from a JWT token."""
    user_id: str
    role: str  # admin, operator, resident, guest
    name: str = ""
    issued_at: float = 0.0


def create_token(user_id: str, role: str, name: str = "") -> str:
    """Create a signed JWT token for a user."""
    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "iat": time.time(),
        "exp": time.time() + TOKEN_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[AuthenticatedUser]:
    """Verify a JWT token and return the authenticated user, or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return AuthenticatedUser(
            user_id=payload["sub"],
            role=payload.get("role", "guest"),
            name=payload.get("name", ""),
            issued_at=payload.get("iat", 0),
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency: extract and verify the current user from JWT.
    Checks Authorization header first, then falls back to cookie.
    """
    token = None

    # 1. Try Bearer token from Authorization header
    if credentials and credentials.credentials:
        token = credentials.credentials

    # 2. Fallback: try cookie
    if not token:
        token = request.cookies.get("lha_session")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a Bearer token or session cookie.",
        )

    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    return user


async def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency: require admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


async def require_operator_or_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency: require admin or operator role."""
    if user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Admin or operator access required.")
    return user


async def require_resident(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency: require at least resident role (admin, operator, or resident)."""
    if user.role not in ("admin", "operator", "resident"):
        raise HTTPException(status_code=403, detail="Resident access required.")
    return user


# --- PIN hashing utilities ---

def hash_pin(pin: str) -> str:
    """Hash a PIN using bcrypt."""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    """Verify a PIN against its bcrypt hash (timing-safe)."""
    try:
        return bcrypt.checkpw(pin.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Local-network detection (used by the guest-PIN auto-login flow)
#
# Hard rule: never trust X-Forwarded-For / X-Real-IP. Read only the actual
# TCP peer (request.client.host). This defeats spoofing through a proxy
# header AND DNS rebinding — rebinding can change the hostname but cannot
# change the source IP of the TCP connection.
# ---------------------------------------------------------------------------

import ipaddress as _ipaddress  # noqa: E402


_LOCAL_NETS = (
    _ipaddress.ip_network("10.0.0.0/8"),
    _ipaddress.ip_network("172.16.0.0/12"),
    _ipaddress.ip_network("192.168.0.0/16"),
    _ipaddress.ip_network("169.254.0.0/16"),  # IPv4 link-local
    _ipaddress.ip_network("fc00::/7"),         # IPv6 unique-local
    _ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
)


def is_request_from_local_network(request: Request) -> bool:
    """
    Returns True if the request's TCP peer is on a private/link-local
    network. Strict RFC1918 + IPv6 ULA/link-local — not Python's
    ipaddress.is_private which mis-includes TEST-NET ranges like
    203.0.113.0/24.

    Loopback (127.0.0.1, ::1) is rejected by default — a developer hitting
    localhost should NOT get a free guest session. Set
    ``LHA_ALLOW_LOOPBACK_GUEST=1`` for dev-only override. The test
    pseudo-hostname "testclient" / "localhost" is treated as loopback
    for the same dev override.

    Use this BEFORE any auth check on guest-only endpoints. Header values
    are deliberately ignored — only request.client.host matters.
    """
    if not request.client:
        return False
    host = request.client.host
    allow_loopback = os.environ.get("LHA_ALLOW_LOOPBACK_GUEST") == "1"
    try:
        ip = _ipaddress.ip_address(host)
    except ValueError:
        # Starlette TestClient peer is "testclient" (not an IP). Treat as
        # loopback for dev/test only.
        if host in ("testclient", "localhost") and allow_loopback:
            return True
        return False
    if ip.is_loopback:
        return allow_loopback
    return any(ip in net for net in _LOCAL_NETS)


# Issue a JWT for a guest device. The "gpe" (guest-pin-epoch) claim
# matches secret_store.get_guest_pin_epoch() at issuance time; rotating
# or disabling the guest PIN bumps the epoch on the server, instantly
# invalidating every live guest token on the next request.
def create_guest_token(user_id: str, guest_pin_epoch: int) -> str:
    payload = {
        "sub": user_id,
        "role": "guest",
        "name": "guest",
        "iat": time.time(),
        "exp": time.time() + TOKEN_EXPIRY_SECONDS,
        "gpe": guest_pin_epoch,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_guest_token_epoch(token: str, current_epoch: int) -> bool:
    """For guest tokens only: also verifies the gpe claim matches the
    current server-side epoch. Returns False if expired, signed wrong, or
    revoked by an epoch bump."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return (
            payload.get("role") == "guest"
            and payload.get("gpe") == current_epoch
        )
    except jwt.InvalidTokenError:
        return False
