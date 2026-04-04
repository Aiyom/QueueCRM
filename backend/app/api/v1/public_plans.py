"""Public plans endpoint — no auth required, used by marketing site."""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DBSession
from app.models.plan_config import PlanConfig

router = APIRouter(prefix="/plans", tags=["plans"])


class PublicPlanOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_ar: Optional[str] = None
    name_ru: Optional[str] = None
    price_usd: float
    features: Optional[list] = None
    sort_order: int


@router.get("/", response_model=List[PublicPlanOut])
async def list_public_plans(db: DBSession) -> List[PublicPlanOut]:
    """Returns all active plans. Public — no auth required."""
    result = await db.execute(
        select(PlanConfig)
        .where(PlanConfig.is_active == True)  # noqa: E712
        .order_by(PlanConfig.sort_order, PlanConfig.created_at)
    )
    plans = result.scalars().all()
    return [
        PublicPlanOut(
            id=str(p.id),
            slug=p.slug,
            name_en=p.name_en,
            name_ar=p.name_ar,
            name_ru=p.name_ru,
            price_usd=float(p.price_usd),
            features=p.features,
            sort_order=p.sort_order,
        )
        for p in plans
    ]
