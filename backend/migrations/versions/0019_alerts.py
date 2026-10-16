"""alerts

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019'
down_revision: Union[str, Sequence[str], None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('league_id', sa.String(), nullable=False),
        sa.Column('roster_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('dedupe_key', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('why', sa.String(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.league_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('league_id', 'roster_id', 'dedupe_key', name='uq_alerts_event'),
    )
    op.create_index('ix_alerts_team_created', 'alerts', ['league_id', 'roster_id', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_alerts_team_created', table_name='alerts')
    op.drop_table('alerts')
