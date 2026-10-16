"""game conditions

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017'
down_revision: Union[str, Sequence[str], None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('nfl_games', sa.Column('roof', sa.String(), nullable=True))
    op.add_column('nfl_games', sa.Column('surface', sa.String(), nullable=True))
    op.add_column('nfl_games', sa.Column('stadium', sa.String(), nullable=True))
    op.add_column('nfl_games', sa.Column('temp', sa.Integer(), nullable=True))
    op.add_column('nfl_games', sa.Column('wind', sa.Integer(), nullable=True))
    op.add_column('nfl_games', sa.Column('spread_line', sa.Float(), nullable=True))
    op.add_column('nfl_games', sa.Column('total_line', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for column in ('total_line', 'spread_line', 'wind', 'temp', 'stadium', 'surface', 'roof'):
        op.drop_column('nfl_games', column)
