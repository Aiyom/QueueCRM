"""Tenant settings endpoints: languages, integrations."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import DBSession, TenantAdmin, TenantUser, get_tenant_id
from app.models.tenant import Tenant
from app.schemas.settings import TenantSettingsResponse, TenantSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=TenantSettingsResponse)
async def get_settings(payload: TenantUser, db: DBSession):
    tenant_id = get_tenant_id(payload)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise HTTPException(404, detail="Tenant not found")
    return TenantSettingsResponse.model_validate(tenant)


@router.patch("/", response_model=TenantSettingsResponse)
async def update_settings(
    body: TenantSettingsUpdate,
    payload: TenantAdmin,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise HTTPException(404, detail="Tenant not found")

    if body.enabled_languages is not None:
        tenant.enabled_languages = body.enabled_languages
    if body.telegram_bot_token is not None:
        tenant.telegram_bot_token = body.telegram_bot_token or None
    if body.d360_api_key is not None:
        tenant.d360_api_key = body.d360_api_key or None
    if body.d360_channel_id is not None:
        tenant.d360_channel_id = body.d360_channel_id or None
    if body.manager_telegram_chat_id is not None:
        tenant.manager_telegram_chat_id = body.manager_telegram_chat_id or None

    await db.commit()
    await db.refresh(tenant)
    return TenantSettingsResponse.model_validate(tenant)
