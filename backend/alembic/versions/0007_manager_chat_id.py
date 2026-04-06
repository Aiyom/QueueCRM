"""Add manager_telegram_chat_id to tenants.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("manager_telegram_chat_id", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "manager_telegram_chat_id")
