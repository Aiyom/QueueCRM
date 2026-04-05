import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base
from app.models.whatsapp_session import SessionState


class TelegramSession(Base):
    __tablename__ = "telegram_sessions"

    __table_args__ = (
        UniqueConstraint("tenant_id", "telegram_chat_id", name="uq_telegram_session_tenant_chat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Telegram chat id (string to be safe with large int IDs)
    telegram_chat_id: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[SessionState] = mapped_column(
        String, nullable=False, default=SessionState.idle
    )
    context: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
