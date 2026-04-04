"""CRM: customer management endpoints."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, and_

from app.core.deps import DBSession, TenantUser, TenantAdmin, get_tenant_id
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    SegmentStatsResponse,
)

router = APIRouter(prefix="/customers", tags=["customers"])


# ---------------------------------------------------------------------------
# List with search + pagination
# ---------------------------------------------------------------------------


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    payload: TenantUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_vip: Optional[bool] = Query(None),
):
    tenant_id = get_tenant_id(payload)
    filters = [Customer.tenant_id == tenant_id]

    if search:
        term = f"%{search}%"
        filters.append(
            Customer.phone.ilike(term) | Customer.name.ilike(term)
        )
    if is_vip is not None:
        filters.append(Customer.is_vip == is_vip)

    total_result = await db.execute(
        select(func.count(Customer.id)).where(and_(*filters))
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Customer)
        .where(and_(*filters))
        .order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    customers = list(result.scalars().all())

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Segment stats
# ---------------------------------------------------------------------------


@router.get("/segments/stats", response_model=SegmentStatsResponse)
async def segments_stats(payload: TenantUser, db: DBSession):
    tenant_id = get_tenant_id(payload)

    total = await db.scalar(
        select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)
    ) or 0

    vip = await db.scalar(
        select(func.count(Customer.id)).where(
            and_(Customer.tenant_id == tenant_id, Customer.is_vip == True)  # noqa: E712
        )
    ) or 0

    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    new_this_month = await db.scalar(
        select(func.count(Customer.id)).where(
            and_(
                Customer.tenant_id == tenant_id,
                Customer.created_at >= month_start,
            )
        )
    ) or 0

    avg_visits_result = await db.scalar(
        select(func.avg(Customer.total_visits)).where(Customer.tenant_id == tenant_id)
    )
    avg_spent_result = await db.scalar(
        select(func.avg(Customer.total_spent)).where(Customer.tenant_id == tenant_id)
    )

    return SegmentStatsResponse(
        total_customers=total,
        vip_customers=vip,
        new_this_month=new_this_month,
        avg_visits=round(float(avg_visits_result or 0), 1),
        avg_spent=round(float(avg_spent_result or 0), 2),
    )


# ---------------------------------------------------------------------------
# Single customer CRUD
# ---------------------------------------------------------------------------


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    payload: TenantUser,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    customer = await db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(
    body: CustomerCreate,
    payload: TenantUser,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)

    # Check uniqueness
    existing = await db.scalar(
        select(Customer).where(
            and_(Customer.tenant_id == tenant_id, Customer.phone == body.phone)
        )
    )
    if existing:
        raise HTTPException(409, detail="Customer with this phone already exists")

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        phone=body.phone,
        name=body.name,
        notes=body.notes,
        is_vip=body.is_vip,
        vip_set_manually=body.is_vip,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    payload: TenantAdmin,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    customer = await db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(404, detail="Customer not found")

    if body.name is not None:
        customer.name = body.name
    if body.notes is not None:
        customer.notes = body.notes
    if body.is_vip is not None:
        customer.is_vip = body.is_vip
        customer.vip_set_manually = True

    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)
