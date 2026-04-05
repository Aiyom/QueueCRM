import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class SessionState(str, enum.Enum):
    idle = "idle"
    selecting_service = "selecting_service"
    in_queue = "in_queue"
    being_served = "being_served"
    done = "done"
    # Appointment booking flow
    booking_date = "booking_date"
    booking_service = "booking_service"
    booking_time = "booking_time"
    my_appointments = "my_appointments"


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[SessionState] = mapped_column(
        nullable=False, default=SessionState.idle
    )
    context: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="whatsapp_sessions")  # noqa: F821
    customer: Mapped["Customer"] = relationship(back_populates="whatsapp_sessions")  # noqa: F821
