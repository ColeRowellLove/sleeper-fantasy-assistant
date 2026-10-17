"""index one player's year of stats and projections

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-17 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: Union[str, Sequence[str], None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: the player pop-up reads one player across a season."""
    op.create_index(
        'ix_player_week_stats_player_season', 'player_week_stats', ['player_id', 'season']
    )
    op.create_index(
        'ix_player_projections_player_season', 'player_projections', ['player_id', 'season']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_player_projections_player_season', table_name='player_projections')
    op.drop_index('ix_player_week_stats_player_season', table_name='player_week_stats')
