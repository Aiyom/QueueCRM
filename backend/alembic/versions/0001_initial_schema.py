"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums ---
    # Create enums idempotently — one DO block per call (asyncpg limit: 1 statement per execute)
    _do = lambda sql: op.execute(sa.text(sql))  # noqa: E731
    _do("DO $$ BEGIN CREATE TYPE queuestatus AS ENUM ('waiting','called','in_service','done','cancelled','no_show'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    _do("DO $$ BEGIN CREATE TYPE sessionstate AS ENUM ('idle','selecting_service','in_queue','being_served','done'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    _do("DO $$ BEGIN CREATE TYPE staffrole AS ENUM ('admin','operator'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    _do("DO $$ BEGIN CREATE TYPE subscriptionplan AS ENUM ('starter','pro','business','enterprise'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    _do("DO $$ BEGIN CREATE TYPE subscriptionstatus AS ENUM ('trial','active','past_due','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    _do("DO $$ BEGIN CREATE TYPE businesstype AS ENUM ('auto_service','barbershop','beauty_salon'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # Reference types for column definitions (create_type=False — already created above)
    queue_status = postgresql.ENUM(name="queuestatus", create_type=False)
    session_state = postgresql.ENUM(name="sessionstate", create_type=False)
    staff_role = postgresql.ENUM(name="staffrole", create_type=False)
    subscription_plan = postgresql.ENUM(name="subscriptionplan", create_type=False)
    subscription_status = postgresql.ENUM(name="subscriptionstatus", create_type=False)

    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("business_type", postgresql.ENUM(name="businesstype", create_type=False), nullable=False, server_default="auto_service"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_accepting_queue", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("d360_api_key", sa.String(), nullable=True),
        sa.Column("d360_channel_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    # --- services ---
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name_ar", sa.String(), nullable=False),
        sa.Column("name_en", sa.String(), nullable=False),
        sa.Column("avg_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )

    # --- super_admins ---
    op.create_table(
        "super_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_super_admins_email"),
    )

    # --- customers ---
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("is_vip", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vip_set_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_spent", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("preferred_language", sa.String(), nullable=False, server_default="ar"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_customer_tenant_phone"),
    )

    # --- staff_users ---
    op.create_table(
        "staff_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role", staff_role, nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("email", name="uq_staff_users_email"),
    )

    # --- queue_entries ---
    op.create_table(
        "queue_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", queue_status, nullable=False, server_default="waiting"),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="SET NULL"),
    )

    # --- whatsapp_sessions ---
    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", session_state, nullable=False, server_default="idle"),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
    )

    # --- tenant_subscriptions ---
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", subscription_plan, nullable=False, server_default="starter"),
        sa.Column("status", subscription_status, nullable=False, server_default="trial"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monthly_price_usd", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_subscriptions_tenant_id"),
    )

    # --- Indexes ---
    op.create_index("ix_queue_entries_tenant_status", "queue_entries", ["tenant_id", "status"])
    op.create_index("ix_whatsapp_sessions_customer", "whatsapp_sessions", ["customer_id"])
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"])
    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"])
    op.create_index("ix_staff_users_tenant_id", "staff_users", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("tenant_subscriptions")
    op.drop_table("whatsapp_sessions")
    op.drop_table("queue_entries")
    op.drop_table("staff_users")
    op.drop_table("customers")
    op.drop_table("super_admins")
    op.drop_table("services")
    op.drop_table("tenants")

    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS subscriptionplan")
    op.execute("DROP TYPE IF EXISTS staffrole")
    op.execute("DROP TYPE IF EXISTS sessionstate")
    op.execute("DROP TYPE IF EXISTS queuestatus")
