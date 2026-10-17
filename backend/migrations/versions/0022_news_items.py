"""news headlines from public feeds

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022'
down_revision: Union[str, Sequence[str], None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'news_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('link', sa.String(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('teams', sa.JSON(), nullable=False),
        sa.Column('player_ids', sa.JSON(), nullable=False),
        sa.Column('topics', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_news_items_published_at', 'news_items', ['published_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_news_items_published_at', table_name='news_items')
    op.drop_table('news_items')
