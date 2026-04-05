"""Add enabled_languages and telegram_bot_token to tenants.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column(
            'enabled_languages',
            ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY['ar','en']"),
        ),
    )
    op.add_column(
        'tenants',
        sa.Column('telegram_bot_token', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'telegram_bot_token')
    op.drop_column('tenants', 'enabled_languages')
