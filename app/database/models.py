from datetime import datetime

from sqlalchemy import ARRAY, DateTime, String
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

    def __repr__(self) -> str:
        return f"Article(id={self.id}, title={self.title!r}, sources={self.sources})"
