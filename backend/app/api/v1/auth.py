"""Authentication endpoints: login, refresh, logout, me."""
import uuid

import jwt
from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DBSession, RedisConn
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    delete_refresh_jti,
    refresh_jti_exists,
    rotate_refresh_jti,
    store_refresh_jti,
    verify_password,
)
from app.models.staff_user import StaffUser
from app.models.super_admin import SuperAdmin
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _issue_pair(redis, subject: str, tenant_id: str, role: str) -> TokenResponse:
    access = create_access_token(subject=subject, tenant_id=tenant_id, role=role)
    refresh, jti = create_refresh_token(subject=subject, tenant_id=tenant_id, role=role)
    await store_refresh_jti(redis, jti, subject)
    return TokenResponse(access_token=access, refresh_token=refresh)


async def _validate_refresh(body: RefreshRequest, redis: RedisConn) -> dict:
    """Decode, type-check, and whitelist-check a refresh token. Returns payload."""
    try:
        payload = decode_token(body.refresh_token, verify_exp=True)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    if not await refresh_jti_exists(redis, payload["jti"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or not found",
        )
    return payload


# ---------------------------------------------------------------------------
# Staff login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession, redis: RedisConn):
    """Authenticate a tenant staff user (admin or operator)."""
    result = await db.execute(select(StaffUser).where(StaffUser.email == body.email))
    user: StaffUser | None = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise _CREDENTIALS_ERROR

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Block login if subscription is past_due
    sub_res = await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.tenant_id == user.tenant_id
        )
    )
    sub: TenantSubscription | None = sub_res.scalar_one_or_none()
    if sub and sub.status == SubscriptionStatus.past_due:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Subscription expired. Contact support.",
        )

    return await _issue_pair(
        redis,
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role.value,
    )


# ---------------------------------------------------------------------------
# Super admin login
# ---------------------------------------------------------------------------


@router.post("/super-admin/login", response_model=TokenResponse)
async def super_admin_login(body: LoginRequest, db: DBSession, redis: RedisConn):
    """Authenticate a super admin."""
    result = await db.execute(
        select(SuperAdmin).where(SuperAdmin.email == body.email)
    )
    admin: SuperAdmin | None = result.scalar_one_or_none()

    if not admin or not verify_password(body.password, admin.hashed_password):
        raise _CREDENTIALS_ERROR

    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    return await _issue_pair(
        redis,
        subject=str(admin.id),
        tenant_id="",
        role="super_admin",
    )


# ---------------------------------------------------------------------------
# Token refresh (rotation — returns both tokens)
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, redis: RedisConn):
    """Exchange a refresh token for a new token pair (rotation)."""
    payload = await _validate_refresh(body, redis)

    subject: str = payload["sub"]
    tenant_id: str = payload.get("tid", "")
    role: str = payload["role"]
    old_jti: str = payload["jti"]

    access = create_access_token(subject=subject, tenant_id=tenant_id, role=role)
    new_refresh, new_jti = create_refresh_token(
        subject=subject, tenant_id=tenant_id, role=role
    )
    await rotate_refresh_jti(redis, old_jti, new_jti, subject)

    return TokenResponse(access_token=access, refresh_token=new_refresh)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(body: RefreshRequest, redis: RedisConn):
    """Revoke refresh token. Idempotent — always 200."""
    try:
        payload = decode_token(body.refresh_token, verify_exp=False)
        jti = payload.get("jti")
        if jti:
            await delete_refresh_jti(redis, jti)
    except jwt.PyJWTError:
        pass
    return {"detail": "Logged out"}


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=MeResponse)
async def me(payload: CurrentUser, db: DBSession):  # CurrentUser accepts any role
    """Return current user profile."""
    role: str = payload["role"]
    user_id: str = payload["sub"]

    if role == "super_admin":
        result = await db.execute(
            select(SuperAdmin).where(SuperAdmin.id == uuid.UUID(user_id))
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(404, detail="User not found")
        return MeResponse(
            id=str(admin.id),
            email=admin.email,
            full_name=admin.full_name,
            role="super_admin",
        )

    result = await db.execute(
        select(StaffUser).where(StaffUser.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="User not found")
    return MeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        tenant_id=str(user.tenant_id),
    )
