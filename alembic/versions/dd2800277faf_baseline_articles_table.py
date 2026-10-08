"""baseline: articles table

Revision ID: dd2800277faf
Revises: 
Create Date: 2026-10-08 11:24:40.176833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd2800277faf'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment_count", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("sources", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("articles")
