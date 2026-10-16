"""player trends and weekly stats

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'player_trends',
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('adds', sa.Integer(), nullable=True),
        sa.Column('drops', sa.Integer(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('player_id'),
    )
    op.create_table(
        'player_week_stats',
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('team', sa.String(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('season', 'week', 'player_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('player_week_stats')
    op.drop_table('player_trends')
