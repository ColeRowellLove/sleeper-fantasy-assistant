"""player projections

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'player_projections',
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('team', sa.String(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('season', 'week', 'player_id'),
    )
    op.create_index(
        'ix_player_projections_season_week', 'player_projections', ['season', 'week']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_player_projections_season_week', table_name='player_projections')
    op.drop_table('player_projections')
