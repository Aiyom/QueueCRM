"""WorkSchedule — per-tenant working hours configuration."""
import uuid
from datetime import date, time, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, Integer, String, Time, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class WorkSchedule(Base):
    __tablename__ = "work_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Weekly rule: day_of_week 0=Mon..6=Sun, specific_date=null
    # Override: specific_date set, day_of_week=null
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    specific_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    is_working: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    open_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    close_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    # How many clients can be served simultaneously in one slot
    max_parallel: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="work_schedules")  # noqa: F821
