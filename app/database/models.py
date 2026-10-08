from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)  # HN's own item id
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[int] = mapped_column(default=0)
    comment_count: Mapped[int] = mapped_column(default=0)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    sources: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 1536 dims is fixed by text-embedding-3-small. NULL is the backfill target.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    def __repr__(self) -> str:
        return f"Article(id={self.id}, title={self.title!r}, sources={self.sources})"
