
"""populate_system_registry

Revision ID: 0009_populate_system_registry
Revises: 0008_sys_registry
Create Date: 2025-12-01 13:00:00.000000

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_populate_system_registry'
down_revision: Union[str, None] = '0008_sys_registry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            'system_registry',
            sa.column('resource_type', sa.String),
            sa.column('name', sa.String),
            sa.column('version', sa.String),
            sa.column('description', sa.Text),
            sa.column('location', sa.String),
            sa.column('install_command', sa.Text),
            sa.column('dependencies', sa.JSON),
        ),
        [
            {
                "resource_type": "skill",
                "name": "system_bootstrap",
                "version": "1.0",
                "description": "Initializes an agent's environment by discovering and installing required resources.",
                "location": ".agent/skills/system_bootstrap",
                "install_command": "echo 'system_bootstrap skill is already part of the core agent skills.'",
                "dependencies": None,
            },
            {
                "resource_type": "skill",
                "name": "example_market_analysis",
                "version": "1.0",
                "description": "An example skill for performing market analysis.",
                "location": ".agent/skills/example_market_analysis.py",
                "install_command": "echo 'No installation needed for example_market_analysis.py, it is a single file skill.'",
                "dependencies": None,
            },
            {
                "resource_type": "skill",
                "name": "example_rf_monitoring",
                "version": "1.0",
                "description": "An example skill for monitoring radio frequency signals.",
                "location": ".agent/skills/example_rf_monitoring.py",
                "install_command": "echo 'No installation needed for example_rf_monitoring.py, it is a single file skill.'",
                "dependencies": None,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_registry WHERE name IN ('system_bootstrap', 'example_market_analysis', 'example_rf_monitoring')"
    )
