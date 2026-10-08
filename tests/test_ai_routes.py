from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.database.models import Article
from app.database.session import get_db
from app.main import app
from app.network.openai_client import AiServiceError, get_openai_client


def _article(id: int, title: str = "T", embedding=None, summary=None, url=None):
    return Article(
        id=id, title=title, url=url, author="alice", score=10, comment_count=1,
        item_type="story", sources=["top"],
        posted_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        embedding=embedding, summary=summary,
    )


def _embedding_response(vectors):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


def _override_get_db(db_session):
    def _get_db():
        yield db_session
    return _get_db


@pytest.fixture
def client(db_session):
    """TestClient with the DB and OpenAI client overridden.

    `mock` is attached to the client so tests can assert on API calls.
    """
    mock_openai = AsyncMock()
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_openai_client] = lambda: mock_openai
    test_client = TestClient(app)
    test_client.mock = mock_openai
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unconfigured_client(db_session):
    """TestClient simulating no OPENAI_API_KEY."""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_openai_client] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_related_returns_nearest_articles(client, db_session):
    db_session.add_all([
        _article(1, "query", embedding=[1.0] + [0.0] * 1535),
        _article(2, "near", embedding=[0.9, 0.1] + [0.0] * 1534),
        _article(3, "far", embedding=[0.0, 1.0] + [0.0] * 1534),
    ])
    db_session.commit()

    response = client.get("/articles/1/related")

    assert response.status_code == 200
    titles = [a["title"] for a in response.json()["related"]]
    assert titles == ["near", "far"]


def test_related_excludes_the_requested_article(client, db_session):
    db_session.add_all([
        _article(1, "self", embedding=[1.0] + [0.0] * 1535),
        _article(2, "other", embedding=[1.0] + [0.0] * 1535),
    ])
    db_session.commit()

    response = client.get("/articles/1/related")

    assert [a["id"] for a in response.json()["related"]] == [2]


def test_related_backfills_missing_embeddings_before_searching(client, db_session):
    db_session.add_all([_article(1, "a"), _article(2, "b")])
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response(
        [[1.0] + [0.0] * 1535, [0.9, 0.1] + [0.0] * 1534]
    )

    response = client.get("/articles/1/related")

    assert response.status_code == 200
    client.mock.embeddings.create.assert_awaited_once()
    assert [a["id"] for a in response.json()["related"]] == [2]


def test_related_skips_the_api_when_nothing_needs_embedding(client, db_session):
    # Review Focus 2: an empty input array is an OpenAI API error.
    db_session.add_all([
        _article(1, "a", embedding=[1.0] + [0.0] * 1535),
        _article(2, "b", embedding=[0.5] * 1536),
    ])
    db_session.commit()

    response = client.get("/articles/1/related")

    assert response.status_code == 200
    client.mock.embeddings.create.assert_not_awaited()


def test_related_returns_empty_on_a_single_article_corpus(client, db_session):
    db_session.add(_article(1, "only", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()

    response = client.get("/articles/1/related")

    assert response.status_code == 200
    assert response.json()["related"] == []


def test_related_404s_for_an_unknown_article(client):
    assert client.get("/articles/9999/related").status_code == 404


def test_related_501s_without_an_api_key(unconfigured_client, db_session):
    db_session.add(_article(1, "a", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()

    assert unconfigured_client.get("/articles/1/related").status_code == 501


def test_related_503s_when_embedding_fails(client, db_session):
    db_session.add(_article(1, "a"))
    db_session.commit()
    client.mock.embeddings.create.side_effect = AiServiceError("boom")

    assert client.get("/articles/1/related").status_code == 503
