from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.database.models import Article
from app.database.repository import upsert_articles
from app.database.session import get_db
from app.main import app
from app.routes.articles import seed_if_empty


def _override_get_db(db_session):
    def _get_db():
        yield db_session
    return _get_db


def _seed(db_session):
    upsert_articles(
        db_session,
        [
            {
                "id": 1, "title": "Python tips", "url": "http://a.com", "author": "x",
                "score": 50, "comment_count": 2, "item_type": "story",
                "sources": ["top"], "posted_at": datetime.now(timezone.utc),
            },
            {
                "id": 2, "title": "Rust internals", "url": None, "author": "y",
                "score": 5, "comment_count": 0, "item_type": "story",
                "sources": ["ask"], "posted_at": datetime.now(timezone.utc),
            },
        ],
    )


def test_get_articles_filters_by_keyword(db_session):
    _seed(db_session)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"keyword": "python"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Python tips"
    app.dependency_overrides.clear()


def test_get_article_by_id_returns_404_when_missing(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles/999")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_get_article_by_id_returns_article_when_present(db_session):
    _seed(db_session)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles/1")

    assert response.status_code == 200
    assert response.json()["title"] == "Python tips"
    app.dependency_overrides.clear()


def test_get_articles_rejects_invalid_query_params(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"min_score": "not-a-number"})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_articles_rejects_non_positive_page_size(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"page_size": 0})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_articles_rejects_negative_min_score(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"min_score": -1})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_articles_rejects_unknown_source(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"source": "nonsense"})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_articles_rejects_unknown_sort(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"sort": "invalid_value"})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_articles_accepts_valid_source_and_sort(db_session):
    _seed(db_session)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    response = client.get("/articles", params={"source": "ask", "sort": "posted_at_desc"})

    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [2]
    app.dependency_overrides.clear()


def test_refresh_upserts_and_reports_failures(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    fake_items = [
        ({"id": 10, "title": "New story", "by": "z", "score": 1,
          "descendants": 0, "type": "story", "time": 1700000000}, "top"),
        ({"id": 11, "deleted": True}, "top"),  # skipped by merge_batch
        ({"id": 12, "title": "Flagged", "type": "story",
          "time": 1700000000, "dead": True}, "best"),  # skipped by merge_batch
    ]

    with patch("app.routes.articles.fetch_all", new=AsyncMock(return_value=(fake_items, 3))):
        response = client.post("/articles/refresh")

    assert response.status_code == 200
    body = response.json()
    # failed = 3 network failures + 2 skipped (deleted/dead) items
    assert body == {"fetched": 1, "created": 1, "updated": 0, "failed": 5}
    assert db_session.get(Article, 10) is not None
    assert db_session.get(Article, 11) is None
    assert db_session.get(Article, 12) is None
    app.dependency_overrides.clear()


async def test_seed_if_empty_runs_refresh_when_table_is_empty(db_session):
    fake_items = [
        ({"id": 20, "title": "Bootstrap story", "by": "z", "score": 5,
          "descendants": 1, "type": "story", "time": 1700000000}, "top"),
    ]

    with patch("app.routes.articles.fetch_all", new=AsyncMock(return_value=(fake_items, 0))):
        await seed_if_empty(db_session)

    assert db_session.get(Article, 20) is not None


async def test_seed_if_empty_skips_refresh_when_table_has_data(db_session):
    _seed(db_session)
    fetch_mock = AsyncMock(return_value=([], 0))

    with patch("app.routes.articles.fetch_all", new=fetch_mock):
        await seed_if_empty(db_session)

    fetch_mock.assert_not_called()


async def test_seed_if_empty_swallows_fetch_failure_so_startup_does_not_crash(db_session):
    with patch(
        "app.routes.articles.fetch_all", new=AsyncMock(side_effect=RuntimeError("HN unreachable"))
    ):
        await seed_if_empty(db_session)  # must not raise

    assert db_session.query(Article).count() == 0


def test_unexpected_exception_returns_clean_500(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app, raise_server_exceptions=False)

    with patch("app.routes.articles.query_articles", side_effect=RuntimeError("boom")):
        response = client.get("/articles")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    app.dependency_overrides.clear()
