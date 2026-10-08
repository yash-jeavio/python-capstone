from datetime import datetime, timezone

from app.database.models import Article


def test_ai_columns_default_to_none(db_session):
    article = Article(
        id=1, title="Test", url=None, author="alice", score=10,
        comment_count=2, item_type="story", sources=["top"],
        posted_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(article)
    db_session.commit()

    assert article.summary is None
    assert article.summary_generated_at is None
    assert article.embedding is None


def test_embedding_round_trips_a_vector(db_session):
    article = Article(
        id=2, title="Test", url=None, author="alice", score=10,
        comment_count=2, item_type="story", sources=["top"],
        posted_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc),
        embedding=[0.5] * 1536,
    )
    db_session.add(article)
    db_session.commit()
    db_session.expire(article)

    assert len(article.embedding) == 1536
    assert article.embedding[0] == 0.5
