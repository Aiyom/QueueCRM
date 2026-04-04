import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class BusinessType(str, enum.Enum):
    auto_service = "auto_service"
    barbershop = "barbershop"
    beauty_salon = "beauty_salon"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    business_type: Mapped[BusinessType] = mapped_column(
        nullable=False, default=BusinessType.auto_service
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_accepting_queue: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    d360_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    d360_channel_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    services: Mapped[List["Service"]] = relationship(back_populates="tenant")  # noqa: F821
    customers: Mapped[List["Customer"]] = relationship(back_populates="tenant")  # noqa: F821
    queue_entries: Mapped[List["QueueEntry"]] = relationship(back_populates="tenant")  # noqa: F821
    whatsapp_sessions: Mapped[List["WhatsAppSession"]] = relationship(back_populates="tenant")  # noqa: F821
    staff_users: Mapped[List["StaffUser"]] = relationship(back_populates="tenant")  # noqa: F821
    subscription: Mapped[Optional["TenantSubscription"]] = relationship(back_populates="tenant")  # noqa: F821
