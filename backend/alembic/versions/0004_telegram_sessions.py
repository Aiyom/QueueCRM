"""Add telegram_sessions table and telegram_chat_id to customers.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column('telegram_chat_id', sa.String(), nullable=True),
    )

    op.create_table(
        'telegram_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('telegram_chat_id', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False, server_default='idle'),
        sa.Column('context', JSONB(), nullable=False, server_default='{}'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('tenant_id', 'telegram_chat_id',
                            name='uq_telegram_session_tenant_chat'),
    )


def downgrade() -> None:
    op.drop_table('telegram_sessions')
    op.drop_column('customers', 'telegram_chat_id')
