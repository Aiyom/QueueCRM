"""Global plan catalog managed by super admin."""
import uuid
from typing import List, Optional
from sqlalchemy import String, Numeric, Boolean, Integer, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.core.database import Base


class PlanConfig(Base):
    __tablename__ = "plan_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name_ru: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    # features stored as JSON list of strings
    features: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
