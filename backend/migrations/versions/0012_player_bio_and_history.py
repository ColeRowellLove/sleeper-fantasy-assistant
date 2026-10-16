"""player bio and past-season stats

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-16 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('players', sa.Column('bio', sa.JSON(), nullable=True))
    op.create_table(
        'player_season_stats',
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('games', sa.Integer(), nullable=False),
        sa.Column('stats', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('season', 'player_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('player_season_stats')
    op.drop_column('players', 'bio')
