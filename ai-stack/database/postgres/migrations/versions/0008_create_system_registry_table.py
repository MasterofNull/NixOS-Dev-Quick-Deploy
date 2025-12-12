"""create_system_registry_table

Revision ID: 0008_create_system_registry_table
Revises: 0007_status_flags
Create Date: 2025-12-01 12:00:00.000000

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0008_sys_registry'
down_revision: Union[str, None] = '0007_status_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=False),
        sa.Column('install_command', sa.Text(), nullable=True),
        sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('added_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table_comment(
        'system_registry',
        'Central registry for all discoverable AI-Optimizer resources.',
        schema=None
    )
    op.alter_column(
        'system_registry',
        'location',
        existing_type=sa.String(length=255),
        comment='Git URL for skills/tools, API endpoint for data, or path for schemas.',
        schema=None
    )
    op.alter_column(
        'system_registry',
        'install_command',
        existing_type=sa.Text(),
        comment='A shell command to make the resource usable, e.g., git clone, pip install.',
        schema=None
    )


def downgrade() -> None:
    op.drop_table('system_registry')
