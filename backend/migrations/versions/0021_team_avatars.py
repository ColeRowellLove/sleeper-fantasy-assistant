"""team pictures: manager avatar id and the team's own picture

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0021'
down_revision: Union[str, Sequence[str], None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sleeper_users', sa.Column('avatar', sa.String(), nullable=True))
    op.add_column('user_leagues', sa.Column('team_avatar', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_leagues', 'team_avatar')
    op.drop_column('sleeper_users', 'avatar')
