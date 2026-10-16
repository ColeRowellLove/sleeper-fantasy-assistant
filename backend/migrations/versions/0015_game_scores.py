"""game scores

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-16 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, Sequence[str], None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('nfl_games', sa.Column('home_score', sa.Integer(), nullable=True))
    op.add_column('nfl_games', sa.Column('away_score', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('nfl_games', 'away_score')
    op.drop_column('nfl_games', 'home_score')
