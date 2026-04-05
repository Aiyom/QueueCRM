"""Service (menu item) management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, and_

from app.core.deps import DBSession, TenantAdmin, TenantUser, get_tenant_id
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/", response_model=list[ServiceResponse])
async def list_services(payload: TenantUser, db: DBSession):
    tenant_id = get_tenant_id(payload)
    result = await db.execute(
        select(Service)
        .where(and_(Service.tenant_id == tenant_id, Service.is_active == True))  # noqa: E712
        .order_by(Service.sort_order)
    )
    return [ServiceResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/", response_model=ServiceResponse, status_code=201)
async def create_service(
    body: ServiceCreate,
    payload: TenantAdmin,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    service = Service(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name_ar=body.name_ar,
        name_en=body.name_en,
        name_ru=body.name_ru,
        avg_duration_minutes=body.avg_duration_minutes,
        sort_order=body.sort_order,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return ServiceResponse.model_validate(service)


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdate,
    payload: TenantAdmin,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    service = await db.get(Service, service_id)
    if not service or service.tenant_id != tenant_id:
        raise HTTPException(404, detail="Service not found")

    if body.name_ar is not None:
        service.name_ar = body.name_ar
    if body.name_en is not None:
        service.name_en = body.name_en
    if body.name_ru is not None:
        service.name_ru = body.name_ru
    if body.avg_duration_minutes is not None:
        service.avg_duration_minutes = body.avg_duration_minutes
    if body.is_active is not None:
        service.is_active = body.is_active
    if body.sort_order is not None:
        service.sort_order = body.sort_order

    await db.commit()
    await db.refresh(service)
    return ServiceResponse.model_validate(service)


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: uuid.UUID,
    payload: TenantAdmin,
    db: DBSession,
):
    tenant_id = get_tenant_id(payload)
    service = await db.get(Service, service_id)
    if not service or service.tenant_id != tenant_id:
        raise HTTPException(404, detail="Service not found")
    # Soft delete
    service.is_active = False
    await db.commit()
