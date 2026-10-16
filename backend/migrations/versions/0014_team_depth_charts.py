"""team depth charts

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-16 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'team_depth_charts',
        sa.Column('team', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('chart', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('team'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('team_depth_charts')
