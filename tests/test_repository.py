# tests/test_repository.py
from datetime import datetime, timezone

from app.database.models import Article
from app.database.repository import query_articles, upsert_articles


def _article_dict(**overrides):
    base = {
        "id": 1,
        "title": "Original title",
        "url": "http://example.com",
        "author": "alice",
        "score": 10,
        "comment_count": 1,
        "item_type": "story",
        "sources": ["top"],
        "posted_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


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


def test_upsert_creates_new_articles(db_session):
    created, updated = upsert_articles(db_session, [_article_dict()])

    assert created == 1
    assert updated == 0
    assert db_session.get(Article, 1).score == 10


def test_upsert_updates_existing_article_on_conflict(db_session):
    upsert_articles(db_session, [_article_dict(score=10)])

    created, updated = upsert_articles(
        db_session, [_article_dict(score=25, sources=["top", "best"])]
    )

    assert created == 0
    assert updated == 1
    refreshed = db_session.get(Article, 1)
    assert refreshed.score == 25
    assert sorted(refreshed.sources) == ["best", "top"]


def test_upsert_is_idempotent_when_rerun_with_same_data(db_session):
    upsert_articles(db_session, [_article_dict()])
    created, updated = upsert_articles(db_session, [_article_dict()])

    assert created == 0
    assert updated == 1  # touched, even though values are unchanged
    all_rows = db_session.query(Article).all()
    assert len(all_rows) == 1  # no duplicate row


def test_query_articles_filters_by_keyword_and_min_score(db_session):
    upsert_articles(
        db_session,
        [
            _article_dict(id=1, title="Python tips", score=50),
            _article_dict(id=2, title="Rust internals", score=5),
        ],
    )

    results = query_articles(
        db_session, keyword="python", min_score=None, source=None,
        sort="score_desc", page=1, page_size=10,
    )

    assert [a.id for a in results] == [1]

    results = query_articles(
        db_session, keyword=None, min_score=10, source=None,
        sort="score_desc", page=1, page_size=10,
    )

    assert [a.id for a in results] == [1]


def test_query_articles_filters_by_source_and_paginates(db_session):
    upsert_articles(
        db_session,
        [
            _article_dict(id=1, title="A", score=1, sources=["top"]),
            _article_dict(id=2, title="B", score=2, sources=["ask"]),
            _article_dict(id=3, title="C", score=3, sources=["top", "ask"]),
        ],
    )

    results = query_articles(
        db_session, keyword=None, min_score=None, source="ask",
        sort="score_desc", page=1, page_size=10,
    )
    assert {a.id for a in results} == {2, 3}

    page_1 = query_articles(
        db_session, keyword=None, min_score=None, source=None,
        sort="score_desc", page=1, page_size=2,
    )
    page_2 = query_articles(
        db_session, keyword=None, min_score=None, source=None,
        sort="score_desc", page=2, page_size=2,
    )
    assert [a.id for a in page_1] == [3, 2]
    assert [a.id for a in page_2] == [1]
