"""JWT creation, verification, and Redis whitelist helpers."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis key patterns
_REFRESH_KEY = "refresh:{jti}"  # value = user_id, TTL = 7 days
_IMPERSONATE_KEY = "impersonate:{token}"  # super-admin impersonation


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    subject: str,
    tenant_id: str,
    role: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Short-lived access token (15 min).

    Claims:
      sub   – staff_user.id or super_admin.id (str)
      tid   – tenant_id (str) | None for super admin
      role  – "admin" | "operator" | "super_admin"
      type  – "access"
      jti   – unique id (not stored in Redis; access tokens are stateless)
    """
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "tid": tenant_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": _now(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, tenant_id: str, role: str) -> tuple[str, str]:
    """Long-lived refresh token (7 days).

    Returns (encoded_token, jti). The caller must store jti in Redis.
    """
    jti = str(uuid.uuid4())
    expire = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "tid": tenant_id,
        "role": role,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
        "iat": _now(),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, jti


def decode_token(token: str, *, verify_exp: bool = True) -> dict[str, Any]:
    """Decode and validate JWT. Raises jwt.PyJWTError on failure."""
    options = {"verify_exp": verify_exp}
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options=options,
    )


# ---------------------------------------------------------------------------
# Redis whitelist helpers
# ---------------------------------------------------------------------------


async def store_refresh_jti(redis: Redis, jti: str, user_id: str) -> None:
    """Persist jti → user_id in Redis with TTL = REFRESH_TOKEN_EXPIRE_DAYS."""
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.set(_REFRESH_KEY.format(jti=jti), user_id, ex=ttl)


async def refresh_jti_exists(redis: Redis, jti: str) -> bool:
    """Return True if jti is in the whitelist."""
    return bool(await redis.exists(_REFRESH_KEY.format(jti=jti)))


async def delete_refresh_jti(redis: Redis, jti: str) -> None:
    """Remove jti from whitelist (logout). Idempotent."""
    await redis.delete(_REFRESH_KEY.format(jti=jti))


async def rotate_refresh_jti(
    redis: Redis, old_jti: str, new_jti: str, user_id: str
) -> None:
    """Atomically delete old jti and store new one (token rotation)."""
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    pipe = redis.pipeline()
    pipe.delete(_REFRESH_KEY.format(jti=old_jti))
    pipe.set(_REFRESH_KEY.format(jti=new_jti), user_id, ex=ttl)
    await pipe.execute()
