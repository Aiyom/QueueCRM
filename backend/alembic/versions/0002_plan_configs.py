"""Add plan_configs table and custom price fields.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'plan_configs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(), nullable=False, unique=True),
        sa.Column('name_en', sa.String(), nullable=False),
        sa.Column('name_ar', sa.String(), nullable=True),
        sa.Column('name_ru', sa.String(), nullable=True),
        sa.Column('price_usd', sa.Numeric(8, 2), nullable=False),
        sa.Column('features', JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # discount_pct: integer 0-100, overrides price when set
    op.add_column(
        'tenant_subscriptions',
        sa.Column('discount_pct', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tenant_subscriptions', 'discount_pct')
    op.drop_table('plan_configs')
