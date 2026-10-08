"""add summary and embedding columns

Revision ID: 8636f32cfa86
Revises: dd2800277faf
Create Date: 2026-10-08 11:32:22.492700

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8636f32cfa86'
down_revision: Union[str, Sequence[str], None] = 'dd2800277faf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("articles", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "articles", sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "articles", sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("articles", "embedding")
    op.drop_column("articles", "summary_generated_at")
    op.drop_column("articles", "summary")
    # The extension is left in place: other objects may depend on it.
