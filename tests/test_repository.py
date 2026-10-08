# tests/test_repository.py
from datetime import datetime, timezone

import pytest

from app.database.models import Article
from app.database.repository import (
    articles_missing_embeddings,
    find_similar,
    query_articles,
    store_embeddings,
    store_summary,
    upsert_articles,
)


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


def test_upsert_unions_sources_across_refreshes(db_session):
    # Refresh 1: article is on "top". Refresh 2: it dropped off "top", now on "best".
    upsert_articles(db_session, [_article_dict(sources=["top"])])
    upsert_articles(db_session, [_article_dict(sources=["best"])])

    db_session.expire_all()
    refreshed = db_session.get(Article, 1)
    assert set(refreshed.sources) == {"top", "best"}
    assert len(refreshed.sources) == 2  # deduplicated, nothing dropped

    # Re-seeing an already-recorded list must not introduce duplicates.
    upsert_articles(db_session, [_article_dict(sources=["top", "best"])])
    db_session.expire_all()
    refreshed = db_session.get(Article, 1)
    assert sorted(refreshed.sources) == ["best", "top"]


def test_query_articles_breaks_score_ties_by_id_across_pages(db_session):
    upsert_articles(
        db_session,
        [_article_dict(id=i, title=f"T{i}", score=10) for i in range(1, 6)],
    )

    pages = [
        query_articles(
            db_session, keyword=None, min_score=None, source=None,
            sort="score_desc", page=p, page_size=2,
        )
        for p in (1, 2, 3)
    ]

    assert [[a.id for a in page] for page in pages] == [[5, 4], [3, 2], [1]]


def test_article_timestamps_are_timezone_aware(db_session):
    upsert_articles(db_session, [_article_dict()])

    db_session.expire_all()
    fetched = db_session.get(Article, 1)
    assert fetched.posted_at.utcoffset() is not None
    assert fetched.fetched_at.utcoffset() is not None


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


def _make_article(id: int, title: str = "T", embedding=None, summary=None, score: int = 10):
    return Article(
        id=id, title=title, url=f"https://example.com/{id}", author="alice",
        score=score, comment_count=1, item_type="story", sources=["top"],
        posted_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        embedding=embedding, summary=summary,
    )


def test_articles_missing_embeddings_returns_only_null_rows(db_session):
    db_session.add_all([
        _make_article(1, embedding=None),
        _make_article(2, embedding=[0.1] * 1536),
        _make_article(3, embedding=None),
    ])
    db_session.commit()

    result = articles_missing_embeddings(db_session)

    assert {a.id for a in result} == {1, 3}


def test_articles_missing_embeddings_is_empty_when_all_are_embedded(db_session):
    db_session.add(_make_article(1, embedding=[0.1] * 1536))
    db_session.commit()

    assert articles_missing_embeddings(db_session) == []


def test_store_embeddings_persists_vectors(db_session):
    a, b = _make_article(1), _make_article(2)
    db_session.add_all([a, b])
    db_session.commit()

    store_embeddings(db_session, [(a, [0.1] * 1536), (b, [0.2] * 1536)])
    db_session.expire_all()

    assert articles_missing_embeddings(db_session) == []
    assert db_session.get(Article, 1).embedding[0] == pytest.approx(0.1)


def test_store_summary_persists_summary_timestamp_and_embedding(db_session):
    article = _make_article(1)
    db_session.add(article)
    db_session.commit()

    store_summary(db_session, article, "A summary.", [0.3] * 1536)
    db_session.expire_all()

    stored = db_session.get(Article, 1)
    assert stored.summary == "A summary."
    assert stored.summary_generated_at is not None
    # Summary and its refreshed vector are written together -- a summary must
    # never be visible with a vector that predates it.
    assert stored.embedding[0] == pytest.approx(0.3)


def test_find_similar_orders_by_cosine_distance(db_session):
    query_vector = [1.0] + [0.0] * 1535
    near = [0.9, 0.1] + [0.0] * 1534
    far = [0.0, 1.0] + [0.0] * 1534
    db_session.add_all([
        _make_article(1, title="far", embedding=far),
        _make_article(2, title="near", embedding=near),
    ])
    db_session.commit()

    result = find_similar(db_session, query_vector)

    assert [a.title for a in result] == ["near", "far"]


def test_find_similar_uses_cosine_not_l2_or_inner_product(db_session):
    # Magnitudes are chosen so cosine, L2, and negative-inner-product distance
    # disagree on the ranking -- do not "simplify" these vectors.
    #   query   = (1, 0)
    #   aligned = (0.5, 0)   same direction as query, smaller magnitude
    #   offset  = (0.9, 0.1) slightly off-direction, larger magnitude
    # cosine distance:   aligned 0.0    < offset ~0.006  -> aligned first (required)
    # L2 distance:       offset ~0.141  < aligned 0.5    -> offset first
    # neg inner product: offset -0.9    < aligned -0.5   -> offset first
    query_vector = [1.0] + [0.0] * 1535
    aligned = [0.5, 0.0] + [0.0] * 1534
    offset = [0.9, 0.1] + [0.0] * 1534
    db_session.add_all([
        _make_article(1, title="offset", embedding=offset),
        _make_article(2, title="aligned", embedding=aligned),
    ])
    db_session.commit()

    result = find_similar(db_session, query_vector)

    assert [a.title for a in result] == ["aligned", "offset"]


def test_find_similar_excludes_the_given_article(db_session):
    vector = [1.0] + [0.0] * 1535
    db_session.add_all([
        _make_article(1, title="self", embedding=vector),
        _make_article(2, title="other", embedding=vector),
    ])
    db_session.commit()

    result = find_similar(db_session, vector, exclude_id=1)

    assert [a.id for a in result] == [2]


def test_find_similar_skips_rows_without_embeddings(db_session):
    db_session.add_all([
        _make_article(1, title="embedded", embedding=[1.0] + [0.0] * 1535),
        _make_article(2, title="not embedded", embedding=None),
    ])
    db_session.commit()

    result = find_similar(db_session, [1.0] + [0.0] * 1535)

    assert [a.id for a in result] == [1]


def test_find_similar_on_a_corpus_smaller_than_the_limit(db_session):
    # Review Focus 3: a near-empty corpus must return what exists, not error.
    db_session.add(_make_article(1, embedding=[1.0] + [0.0] * 1535))
    db_session.commit()

    assert len(find_similar(db_session, [1.0] + [0.0] * 1535, limit=5)) == 1


def test_find_similar_returns_empty_when_only_the_excluded_article_exists(db_session):
    vector = [1.0] + [0.0] * 1535
    db_session.add(_make_article(1, embedding=vector))
    db_session.commit()

    assert find_similar(db_session, vector, exclude_id=1) == []
