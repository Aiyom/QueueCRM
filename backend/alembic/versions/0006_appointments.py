"""Add work_schedules and appointments tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=True),
        sa.Column("specific_date", sa.Date, nullable=True),
        sa.Column("is_working", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("open_time", sa.Time, nullable=True),
        sa.Column("close_time", sa.Time, nullable=True),
        sa.Column("max_parallel", sa.Integer, nullable=False, server_default="1"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_work_schedules_tenant_id", "work_schedules", ["tenant_id"])
    op.create_index("ix_work_schedules_specific_date", "work_schedules", ["tenant_id", "specific_date"])
    op.create_index("ix_work_schedules_day_of_week", "work_schedules", ["tenant_id", "day_of_week"])

    op.create_table(
        "appointments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="confirmed"),
        sa.Column("reminder_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("queue_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("queue_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])
    op.create_index("ix_appointments_scheduled_at", "appointments", ["tenant_id", "scheduled_at"])
    op.create_index("ix_appointments_customer_id", "appointments", ["tenant_id", "customer_id"])
    op.create_index("ix_appointments_status", "appointments", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("work_schedules")
