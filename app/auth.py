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
