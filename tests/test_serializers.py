from datetime import datetime, timezone

from app.database.models import Article
from app.routes.serializers import serialize_article


def test_serialize_article_returns_the_api_shape():
    article = Article(
        id=42, title="Rust is fast", url="https://example.com", author="alice",
        score=120, comment_count=7, item_type="story", sources=["top", "best"],
        posted_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert serialize_article(article) == {
        "id": 42, "title": "Rust is fast", "url": "https://example.com",
        "author": "alice", "score": 120, "comment_count": 7,
        "item_type": "story", "sources": ["top", "best"],
        "posted_at": "2026-10-01T12:00:00+00:00",
    }


def test_serialize_article_omits_internal_fields():
    # fetched_at, summary and embedding are internal; the frontend Article type
    # does not declare them and they must not leak into responses.
    article = Article(
        id=1, title="T", url=None, author=None, score=0, comment_count=0,
        item_type="story", sources=["ask"],
        posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        summary="a summary", embedding=[0.1] * 1536,
    )

    result = serialize_article(article)

    assert "fetched_at" not in result
    assert "summary" not in result
    assert "embedding" not in result
