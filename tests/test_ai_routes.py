from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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


def _chat_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


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


def test_summary_returns_a_cached_summary_without_calling_openai(client, db_session):
    # Review Focus 5: the cache is the entire cost-control mechanism.
    db_session.add(_article(1, "a", summary="Already summarized.", embedding=[0.1] * 1536))
    db_session.commit()

    response = client.get("/articles/1/summary")

    assert response.status_code == 200
    assert response.json() == {"summary": "Already summarized."}
    client.mock.chat.completions.create.assert_not_awaited()
    client.mock.embeddings.create.assert_not_awaited()


def test_summary_works_for_a_cached_summary_without_an_api_key(
    unconfigured_client, db_session
):
    # The cache check precedes the key check, so removing a key does not break
    # articles that were already summarized.
    db_session.add(_article(1, "a", summary="Already summarized."))
    db_session.commit()

    response = unconfigured_client.get("/articles/1/summary")

    assert response.status_code == 200
    assert response.json() == {"summary": "Already summarized."}


def test_summary_generates_from_page_text_and_persists(client, db_session):
    db_session.add(_article(1, "Rust is fast", url="https://example.com/rust"))
    db_session.commit()
    client.mock.chat.completions.create.return_value = _chat_response("A summary.")
    client.mock.embeddings.create.return_value = _embedding_response([[0.7] * 1536])

    with patch(
        "app.routes.ai.fetch_article_text", new=AsyncMock(return_value="Article body.")
    ):
        response = client.get("/articles/1/summary")

    assert response.status_code == 200
    assert response.json() == {"summary": "A summary."}

    db_session.expire_all()
    stored = db_session.get(Article, 1)
    assert stored.summary == "A summary."
    assert stored.summary_generated_at is not None
    # The vector is refreshed from title + summary in the same request.
    assert stored.embedding[0] == pytest.approx(0.7)


def test_summary_falls_back_to_comments_when_the_article_has_no_url(client, db_session):
    # Review Focus 1: Ask HN and text posts have url = NULL.
    db_session.add(_article(1, "Ask HN: how do you test?", url=None))
    db_session.commit()
    client.mock.chat.completions.create.return_value = _chat_response("Discussion summary.")
    client.mock.embeddings.create.return_value = _embedding_response([[0.2] * 1536])

    fetch_text = AsyncMock(return_value="should not be called")
    fetch_comments = AsyncMock(return_value=["Use pytest.", "Write fewer mocks."])
    with patch("app.routes.ai.fetch_article_text", new=fetch_text), patch(
        "app.routes.ai.fetch_comments", new=fetch_comments
    ):
        response = client.get("/articles/1/summary")

    assert response.status_code == 200
    assert response.json() == {"summary": "Discussion summary."}
    fetch_text.assert_not_awaited()
    fetch_comments.assert_awaited_once()


def test_summary_falls_back_to_comments_when_the_fetch_fails(client, db_session):
    db_session.add(_article(1, "Paywalled", url="https://example.com/paywall"))
    db_session.commit()
    client.mock.chat.completions.create.return_value = _chat_response("From comments.")
    client.mock.embeddings.create.return_value = _embedding_response([[0.2] * 1536])

    with patch(
        "app.routes.ai.fetch_article_text", new=AsyncMock(return_value=None)
    ), patch(
        "app.routes.ai.fetch_comments", new=AsyncMock(return_value=["A comment."])
    ):
        response = client.get("/articles/1/summary")

    assert response.status_code == 200
    assert response.json() == {"summary": "From comments."}


def test_summary_503s_when_no_content_can_be_retrieved(client, db_session):
    db_session.add(_article(1, "Dead link", url="https://example.com/gone"))
    db_session.commit()

    with patch(
        "app.routes.ai.fetch_article_text", new=AsyncMock(return_value=None)
    ), patch("app.routes.ai.fetch_comments", new=AsyncMock(return_value=[])):
        response = client.get("/articles/1/summary")

    assert response.status_code == 503
    client.mock.chat.completions.create.assert_not_awaited()


def test_summary_truncates_long_content_before_sending(client, db_session):
    db_session.add(_article(1, "Long", url="https://example.com/long"))
    db_session.commit()
    client.mock.chat.completions.create.return_value = _chat_response("A summary.")
    client.mock.embeddings.create.return_value = _embedding_response([[0.2] * 1536])

    with patch(
        "app.routes.ai.fetch_article_text", new=AsyncMock(return_value="word " * 10_000)
    ):
        client.get("/articles/1/summary")

    sent = client.mock.chat.completions.create.await_args.kwargs["messages"][1]["content"]
    assert len(sent) < 13_000


def test_summary_404s_for_an_unknown_article(client):
    assert client.get("/articles/9999/summary").status_code == 404


def test_summary_501s_without_an_api_key(unconfigured_client, db_session):
    db_session.add(_article(1, "a"))
    db_session.commit()

    assert unconfigured_client.get("/articles/1/summary").status_code == 501


def test_summary_503s_when_the_completion_fails(client, db_session):
    db_session.add(_article(1, "a", url="https://example.com/a"))
    db_session.commit()
    client.mock.chat.completions.create.side_effect = AiServiceError("boom")

    with patch(
        "app.routes.ai.fetch_article_text", new=AsyncMock(return_value="Body.")
    ):
        assert client.get("/articles/1/summary").status_code == 503
