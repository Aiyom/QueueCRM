"""Super Admin API — tenant management + plan catalog endpoints."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DBSession, SuperAdmin
from app.models.plan_config import PlanConfig
from app.models.tenant import Tenant
from app.models.tenant_subscription import SubscriptionPlan, SubscriptionStatus, TenantSubscription

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SubscriptionOut(BaseModel):
    id: str
    status: str
    plan: str
    trial_ends_at: str
    current_period_end: Optional[str] = None
    monthly_price_usd: Optional[float] = None
    discount_pct: Optional[int] = None
    notes: Optional[str] = None


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    business_type: str
    phone: str
    is_active: bool
    is_accepting_queue: bool
    d360_api_key: Optional[str] = None
    d360_channel_id: Optional[str] = None
    enabled_languages: List[str] = ["ar", "en"]
    telegram_bot_token: Optional[str] = None
    created_at: str
    subscription: Optional[SubscriptionOut] = None


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    phone: str
    business_type: str = "auto_service"
    d360_api_key: Optional[str] = None
    d360_channel_id: Optional[str] = None


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    d360_api_key: Optional[str] = None
    d360_channel_id: Optional[str] = None


class ExtendTrialRequest(BaseModel):
    days: int


class UpdateSubscriptionRequest(BaseModel):
    plan: Optional[str] = None
    status: Optional[str] = None
    monthly_price_usd: Optional[float] = Field(None, ge=0)
    discount_pct: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


# Plan catalog schemas
class PlanOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_ar: Optional[str] = None
    name_ru: Optional[str] = None
    price_usd: float
    features: Optional[list] = None
    is_active: bool
    sort_order: int


class CreatePlanRequest(BaseModel):
    slug: str
    name_en: str
    name_ar: Optional[str] = None
    name_ru: Optional[str] = None
    price_usd: float = Field(gt=0)
    features: Optional[List[str]] = None
    sort_order: int = 0


class UpdatePlanRequest(BaseModel):
    name_en: Optional[str] = None
    name_ar: Optional[str] = None
    name_ru: Optional[str] = None
    price_usd: Optional[float] = Field(None, gt=0)
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tenant_to_out(tenant: Tenant) -> TenantOut:
    sub = None
    if tenant.subscription:
        s = tenant.subscription
        sub = SubscriptionOut(
            id=str(s.id),
            status=s.status.value,
            plan=s.plan.value,
            trial_ends_at=s.trial_ends_at.isoformat(),
            current_period_end=(
                s.current_period_end.isoformat() if s.current_period_end else None
            ),
            monthly_price_usd=float(s.monthly_price_usd) if s.monthly_price_usd is not None else None,
            discount_pct=s.discount_pct,
            notes=s.notes,
        )
    return TenantOut(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        business_type=tenant.business_type.value,
        phone=tenant.phone,
        is_active=tenant.is_active,
        is_accepting_queue=tenant.is_accepting_queue,
        d360_api_key=tenant.d360_api_key,
        d360_channel_id=tenant.d360_channel_id,
        enabled_languages=tenant.enabled_languages or ["ar", "en"],
        telegram_bot_token=tenant.telegram_bot_token,
        created_at=tenant.created_at.isoformat(),
        subscription=sub,
    )


def _plan_to_out(p: PlanConfig) -> PlanOut:
    return PlanOut(
        id=str(p.id),
        slug=p.slug,
        name_en=p.name_en,
        name_ar=p.name_ar,
        name_ru=p.name_ru,
        price_usd=float(p.price_usd),
        features=p.features,
        is_active=p.is_active,
        sort_order=p.sort_order,
    )


async def _get_tenant_or_404(tenant_id: UUID, db: DBSession) -> Tenant:
    result = await db.execute(
        select(Tenant)
        .where(Tenant.id == tenant_id)
        .options(selectinload(Tenant.subscription))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Tenant routes
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=List[TenantOut])
async def list_tenants(db: DBSession, _: SuperAdmin) -> List[TenantOut]:
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.subscription))
        .order_by(Tenant.created_at.desc())
    )
    return [_tenant_to_out(t) for t in result.scalars().all()]


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(body: CreateTenantRequest, db: DBSession, _: SuperAdmin) -> TenantOut:
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")

    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        phone=body.phone,
        business_type=body.business_type,
        d360_api_key=body.d360_api_key,
        d360_channel_id=body.d360_channel_id,
    )
    db.add(tenant)
    await db.flush()

    sub = TenantSubscription(
        tenant_id=tenant.id,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()

    result = await db.execute(
        select(Tenant)
        .where(Tenant.id == tenant.id)
        .options(selectinload(Tenant.subscription))
    )
    return _tenant_to_out(result.scalar_one())


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: UUID, db: DBSession, _: SuperAdmin) -> TenantOut:
    return _tenant_to_out(await _get_tenant_or_404(tenant_id, db))


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: UUID, body: UpdateTenantRequest, db: DBSession, _: SuperAdmin
) -> TenantOut:
    tenant = await _get_tenant_or_404(tenant_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_out(tenant)


@router.patch("/tenants/{tenant_id}/subscription", response_model=TenantOut)
async def update_subscription(
    tenant_id: UUID, body: UpdateSubscriptionRequest, db: DBSession, _: SuperAdmin
) -> TenantOut:
    """Change plan, set custom price or discount for a tenant."""
    tenant = await _get_tenant_or_404(tenant_id, db)
    if not tenant.subscription:
        raise HTTPException(status_code=400, detail="Tenant has no subscription")

    sub = tenant.subscription
    updates = body.model_dump(exclude_unset=True)

    if "plan" in updates:
        try:
            sub.plan = SubscriptionPlan(updates["plan"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {updates['plan']}")

    if "status" in updates:
        try:
            sub.status = SubscriptionStatus(updates["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}")

    for field in ("monthly_price_usd", "discount_pct", "notes"):
        if field in updates:
            setattr(sub, field, updates[field])

    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_out(tenant)


@router.post("/tenants/{tenant_id}/activate", response_model=TenantOut)
async def activate_tenant(tenant_id: UUID, db: DBSession, _: SuperAdmin) -> TenantOut:
    tenant = await _get_tenant_or_404(tenant_id, db)
    tenant.is_active = True
    if tenant.subscription and tenant.subscription.status == SubscriptionStatus.past_due:
        tenant.subscription.status = SubscriptionStatus.active
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_out(tenant)


@router.post("/tenants/{tenant_id}/deactivate", response_model=TenantOut)
async def deactivate_tenant(tenant_id: UUID, db: DBSession, _: SuperAdmin) -> TenantOut:
    tenant = await _get_tenant_or_404(tenant_id, db)
    tenant.is_active = False
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_out(tenant)


@router.post("/tenants/{tenant_id}/extend-trial", response_model=TenantOut)
async def extend_trial(
    tenant_id: UUID, body: ExtendTrialRequest, db: DBSession, _: SuperAdmin
) -> TenantOut:
    tenant = await _get_tenant_or_404(tenant_id, db)
    if not tenant.subscription:
        raise HTTPException(status_code=400, detail="Tenant has no subscription")
    sub = tenant.subscription
    base = max(sub.trial_ends_at, datetime.now(timezone.utc))
    sub.trial_ends_at = base + timedelta(days=body.days)
    sub.status = SubscriptionStatus.trial
    tenant.is_active = True
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_out(tenant)


# ---------------------------------------------------------------------------
# Plan catalog routes
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=List[PlanOut])
async def list_plans(db: DBSession, _: SuperAdmin) -> List[PlanOut]:
    result = await db.execute(
        select(PlanConfig).order_by(PlanConfig.sort_order, PlanConfig.created_at)
    )
    return [_plan_to_out(p) for p in result.scalars().all()]


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(body: CreatePlanRequest, db: DBSession, _: SuperAdmin) -> PlanOut:
    existing = await db.execute(select(PlanConfig).where(PlanConfig.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Plan slug already exists")

    plan = PlanConfig(**body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: UUID, body: UpdatePlanRequest, db: DBSession, _: SuperAdmin
) -> PlanOut:
    result = await db.execute(select(PlanConfig).where(PlanConfig.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: UUID, db: DBSession, _: SuperAdmin) -> None:
    result = await db.execute(select(PlanConfig).where(PlanConfig.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = False
    await db.commit()
