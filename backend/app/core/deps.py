"""FastAPI dependency injection: DB, Redis, current user, tenant guard."""
from typing import Annotated, AsyncGenerator
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

_redis_pool: Redis | None = None


def set_redis_pool(pool: Redis) -> None:
    """Called from lifespan to inject the shared Redis connection."""
    global _redis_pool
    _redis_pool = pool


async def get_redis() -> Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialised")
    return _redis_pool


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ---------------------------------------------------------------------------
# Current user payload (stateless — only validates signature + expiry)
# ---------------------------------------------------------------------------


async def get_token_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> dict:
    token = _extract_token(credentials)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    return payload


# ---------------------------------------------------------------------------
# Role-based guards
# ---------------------------------------------------------------------------


async def get_current_user(
    payload: Annotated[dict, Depends(get_token_payload)],
) -> dict:
    """Returns token payload for any authenticated staff user or super admin."""
    return payload


async def get_current_tenant_user(
    payload: Annotated[dict, Depends(get_token_payload)],
) -> dict:
    """Requires a tenant-scoped user (admin or operator). Blocks super_admin."""
    role = payload.get("role")
    if role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account required",
        )
    return payload


async def require_tenant_admin(
    payload: Annotated[dict, Depends(get_current_tenant_user)],
) -> dict:
    """Requires role == admin within a tenant."""
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return payload


async def require_super_admin(
    payload: Annotated[dict, Depends(get_token_payload)],
) -> dict:
    """Requires super_admin role."""
    if payload.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return payload


# ---------------------------------------------------------------------------
# Typed shortcuts used in route handlers
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisConn = Annotated[Redis, Depends(get_redis)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
TenantUser = Annotated[dict, Depends(get_current_tenant_user)]
TenantAdmin = Annotated[dict, Depends(require_tenant_admin)]
SuperAdmin = Annotated[dict, Depends(require_super_admin)]


def get_tenant_id(payload: dict) -> UUID:
    """Extract and validate tenant_id from token payload."""
    tid = payload.get("tid")
    if not tid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context missing from token",
        )
    return UUID(tid)
