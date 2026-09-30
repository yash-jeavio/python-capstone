# tests/test_repository.py
from datetime import datetime, timezone

from app.database.models import Article


def test_article_sources_array_round_trips(db_session):
    article = Article(
        id=1,
        title="Show HN: A thing",
        url=None,
        author="alice",
        score=42,
        comment_count=3,
        item_type="story",
        sources=["show", "best"],
        posted_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(article)
    db_session.commit()

    fetched = db_session.get(Article, 1)
    assert fetched is not None
    assert fetched.sources == ["show", "best"]
    assert fetched.url is None
