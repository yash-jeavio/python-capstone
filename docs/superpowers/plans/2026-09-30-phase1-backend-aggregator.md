# Hacker News Backend Aggregator (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + PostgreSQL backend that fetches stories from the real Hacker News public API, stores them (deduped/merged across lists), and exposes them through a filterable REST API — no AI features.

**Architecture:** A layered `app/` package: `network/` (HN API client, async), `domains/` (framework-agnostic dedup/merge logic), `database/` (SQLAlchemy models + Postgres upsert), `routes/` (FastAPI endpoints). `domains/` never imports SQLAlchemy, FastAPI, or an HTTP client — it takes plain dicts in, returns plain dicts out.

**Tech Stack:** Python, FastAPI, Uvicorn, SQLAlchemy 2.0, PostgreSQL (Docker), httpx (async HTTP client), pydantic-settings, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-09-30-phase1-backend-aggregator-design.md`

## Global Constraints

- Framework is FastAPI, not Flask (async-native, automatic validation from type hints).
- Database is PostgreSQL only — dev and test both run in Docker containers, never SQLite (the `sources` column requires a native Postgres `ARRAY` type).
- Dependencies are managed via `pyproject.toml` + `uv`, not `requirements.txt`.
- `app/domains/article.py` must not import SQLAlchemy, FastAPI, or an HTTP client — plain data in, plain data out.
- Only three endpoints exist: `POST /articles/refresh`, `GET /articles`, `GET /articles/{id}`. No `POST`/`PUT`/`DELETE` on individual articles.
- Refresh is on-demand only — no scheduled/background jobs in this phase.
- Only the `top`, `best`, `ask`, and `show` HN story lists are fetched — `new` is explicitly excluded.
- `articles.id` is HN's own item id (not auto-generated) — upsert on conflict, never a duplicate row for the same HN id.

## Review Focus

- **Same story returned by two lists in one refresh** (e.g. `top` and `best` both include item 123) — must become one row with `sources = ['top', 'best']`, not two racing upserts. Pinned in Task 4 (domain merge).
- **Missing optional HN fields** (Ask HN posts have no `url`; a brand-new item may have no `score`/`descendants` yet) — normalization must default these instead of raising `KeyError`. Pinned in Task 4.
- **Partial refresh failure** (some HN item lookups time out/error) must still commit the articles that *did* succeed, not abort the whole batch. Pinned in Task 5 (network layer) and Task 7 (route-level: `created` succeeds while `failed` is reported).
- **Invalid pagination/filter params** (`page_size=0`, negative `min_score`) must not crash or return unbounded results. Pinned in Task 7.
- **Re-running `/articles/refresh` with no real changes** must be idempotent — same scores update to the same values, no duplicate rows, `sources` unchanged — not silently skipped or duplicated. Pinned in Task 6 (automated, at the repository level) and Task 8 (manual end-to-end verification against the real HN API).

---

## File Structure

```
hacker-news-capstone/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── models.py
│   │   └── repository.py        # upsert + query logic (kept separate from schema)
│   ├── domains/
│   │   ├── __init__.py
│   │   └── article.py
│   ├── network/
│   │   ├── __init__.py
│   │   └── hn_client.py
│   └── routes/
│       ├── __init__.py
│       └── articles.py
├── tests/
│   ├── conftest.py
│   ├── test_article_domain.py
│   ├── test_hn_client.py
│   ├── test_repository.py
│   └── test_articles_routes.py
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `app/__init__.py`, `app/common/__init__.py`, `app/database/__init__.py`, `app/domains/__init__.py`, `app/network/__init__.py`, `app/routes/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: an installable `app` package; `uv run pytest` runs (0 tests, no errors).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "hacker-news-capstone"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "pydantic-settings>=2.4",
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
*.egg-info/
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`**

```
DATABASE_URL=postgresql+psycopg2://hn_user:hn_password@localhost:5435/hn_capstone
TEST_DATABASE_URL=postgresql+psycopg2://hn_user:hn_password@localhost:5434/hn_capstone_test
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Hacker News Backend Aggregator (Phase 1)

Fetches stories from the public Hacker News API, stores them in PostgreSQL,
and exposes them through a filterable REST API. No AI features (see Phase 2).

## Setup

1. Copy `.env.example` to `.env`.
2. `docker compose up -d` — starts dev Postgres (host port 5435 -> container 5432) and test Postgres (host port 5434 -> container 5432). Non-standard host ports are deliberate: this machine already has a native Homebrew Postgres service bound to localhost:5432 from an earlier project, so these containers avoid it entirely.
3. `uv sync` — installs dependencies.
4. `uv run uvicorn app.main:app --reload` — starts the API at http://127.0.0.1:8000.
5. `uv run pytest` — runs the test suite (uses the test Postgres container).
```

- [ ] **Step 5: Create empty `__init__.py` files**

```bash
touch app/__init__.py app/common/__init__.py app/database/__init__.py \
      app/domains/__init__.py app/network/__init__.py app/routes/__init__.py \
      tests/__init__.py
```

- [ ] **Step 6: Verify the scaffold**

Run: `uv sync && uv run pytest`
Expected: dependencies install cleanly; pytest reports `no tests ran` (exit code 5), not an import error.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example README.md app tests
git commit -m "chore: project scaffolding"
```

---

### Task 2: PostgreSQL via Docker + settings

**Files:**
- Create: `docker-compose.yml`
- Create: `.env` (local only — not committed)
- Create: `app/common/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` class (importable as `from app.common.config import get_settings`) with `.database_url: str` and `.test_database_url: str`.

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: hn_user
      POSTGRES_PASSWORD: hn_password
      POSTGRES_DB: hn_capstone
    ports:
      - "5435:5432"
    volumes:
      - hn_db_data:/var/lib/postgresql/data

  test-db:
    image: postgres:16
    environment:
      POSTGRES_USER: hn_user
      POSTGRES_PASSWORD: hn_password
      POSTGRES_DB: hn_capstone_test
    ports:
      - "5434:5432"
    # no volume — disposable, wiped every time the container is recreated

volumes:
  hn_db_data:
```

- [ ] **Step 2: Start the containers and verify**

Run: `docker compose up -d && docker compose ps`
Expected: both `db` and `test-db` show `running`/`healthy`.

- [ ] **Step 3: Create `.env` (copy from example, not committed)**

```bash
cp .env.example .env
```

- [ ] **Step 4: Write the failing test for settings**

```python
# tests/test_config.py
from app.common.config import get_settings


def test_settings_load_database_urls():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.test_database_url.startswith("postgresql")
    assert settings.database_url != settings.test_database_url
```

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.common.config'`

- [ ] **Step 6: Implement `app/common/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    test_database_url: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Verify a real connection to the dev container**

Run: `uv run python -c "from sqlalchemy import create_engine, text; from app.common.config import get_settings; e = create_engine(get_settings().database_url); print(e.connect().execute(text('SELECT 1')).scalar())"`
Expected: prints `1`

- [ ] **Step 9: Commit**

```bash
git add docker-compose.yml .env.example app/common/config.py tests/test_config.py
git commit -m "feat: postgres containers + settings"
```

---

### Task 3: Database models, session, and test fixtures

**Files:**
- Create: `app/database/session.py`
- Create: `app/database/models.py`
- Create: `tests/conftest.py`
- Test: `tests/test_repository.py` (schema round-trip only — full repository logic is Task 6)

**Interfaces:**
- Produces: `Base` (declarative base), `Article` ORM model with columns exactly as in the spec's data model table, `engine_for(url: str)` and `session_factory_for(engine)` helpers, plus a production-ready `engine`, `SessionLocal`, and `get_db()` FastAPI dependency — all in `session.py`, so Task 7's routes can `from app.database.session import get_db` directly with no circular import back to `main.py`.
- Produces: a `db_session` pytest fixture (in `conftest.py`) that any later test can depend on — creates all tables against `TEST_DATABASE_URL` before yielding a session, drops them after. This fixture builds its own engine independently of `get_db`/`SessionLocal` above (it must point at the *test* database, never the dev one).

- [ ] **Step 1: Implement `app/database/session.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.common.config import get_settings


class Base(DeclarativeBase):
    pass


def engine_for(database_url: str):
    return create_engine(database_url)


def session_factory_for(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Production engine/session, built from DATABASE_URL (not TEST_DATABASE_URL).
# Importing this module does not open a connection yet -- create_engine()
# is lazy, so this is safe even before the dev Postgres container is up.
engine = engine_for(get_settings().database_url)
SessionLocal = session_factory_for(engine)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Implement `app/database/models.py`**

```python
from datetime import datetime

from sqlalchemy import ARRAY, String
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
    posted_at: Mapped[datetime] = mapped_column(nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"Article(id={self.id}, title={self.title!r}, sources={self.sources})"
```

- [ ] **Step 3: Write `tests/conftest.py`**

```python
import pytest

from app.common.config import get_settings
from app.database.session import Base, engine_for, session_factory_for


@pytest.fixture
def db_session():
    engine = engine_for(get_settings().test_database_url)
    Base.metadata.create_all(engine)
    session_factory = session_factory_for(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
```

- [ ] **Step 4: Write the failing schema round-trip test**

```python
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
```

- [ ] **Step 5: Run test to verify it fails first (containers not yet reachable, or model missing)**

Run: `uv run pytest tests/test_repository.py -v`
Expected: FAIL (before Step 2/3 are in place) or PASS once they are — if it fails after Step 2/3, the error message will point at the actual problem (e.g. connection refused means `docker compose up -d` from Task 2 needs to be running).

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_repository.py -v`
Expected: PASS — confirms the Postgres `ARRAY` column and nullable `url` both round-trip correctly.

- [ ] **Step 7: Commit**

```bash
git add app/database/session.py app/database/models.py tests/conftest.py tests/test_repository.py
git commit -m "feat: article model, session, and db test fixture"
```

---

### Task 4: Domain logic — normalize and merge (framework-agnostic)

**Files:**
- Create: `app/domains/article.py`
- Test: `tests/test_article_domain.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the framework-agnostic core — no imports from `app.database` or `app.network`).
- Produces: `normalize_item(raw_item: dict, source: str) -> dict` and `merge_batch(items: list[tuple[dict, str]]) -> list[dict]`. Each returned dict has keys: `id, title, url, author, score, comment_count, item_type, sources, posted_at` (a `datetime`), ready to hand to the repository layer (Task 6) for upsert.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_article_domain.py
from datetime import datetime, timezone

from app.domains.article import merge_batch, normalize_item


def test_normalize_item_maps_hn_fields():
    raw = {
        "id": 1,
        "title": "Y Combinator",
        "url": "http://ycombinator.com",
        "by": "pg",
        "score": 57,
        "descendants": 3,
        "type": "story",
        "time": 1160418111,
    }
    result = normalize_item(raw, source="top")

    assert result["id"] == 1
    assert result["title"] == "Y Combinator"
    assert result["url"] == "http://ycombinator.com"
    assert result["author"] == "pg"
    assert result["score"] == 57
    assert result["comment_count"] == 3
    assert result["item_type"] == "story"
    assert result["sources"] == ["top"]
    assert result["posted_at"] == datetime.fromtimestamp(1160418111, tz=timezone.utc)


def test_normalize_item_defaults_missing_optional_fields():
    # Ask HN posts have no url; a brand new item may have no score/descendants yet
    raw = {"id": 2, "title": "Ask HN: anything", "by": "bob", "type": "story", "time": 1700000000}
    result = normalize_item(raw, source="ask")

    assert result["url"] is None
    assert result["score"] == 0
    assert result["comment_count"] == 0


def test_merge_batch_combines_sources_for_duplicate_id_in_same_batch():
    raw_top = {"id": 5, "title": "Popular", "by": "x", "score": 10,
               "descendants": 1, "type": "story", "time": 1700000000}
    raw_best = {"id": 5, "title": "Popular", "by": "x", "score": 15,
                "descendants": 2, "type": "story", "time": 1700000000}

    merged = merge_batch([(raw_top, "top"), (raw_best, "best")])

    assert len(merged) == 1
    assert merged[0]["id"] == 5
    assert sorted(merged[0]["sources"]) == ["best", "top"]
    # last-seen values win for fields that change over time
    assert merged[0]["score"] == 15
    assert merged[0]["comment_count"] == 2


def test_merge_batch_keeps_distinct_ids_separate():
    raw_a = {"id": 1, "title": "A", "by": "x", "score": 1, "descendants": 0,
             "type": "story", "time": 1700000000}
    raw_b = {"id": 2, "title": "B", "by": "y", "score": 2, "descendants": 0,
             "type": "story", "time": 1700000000}

    merged = merge_batch([(raw_a, "top"), (raw_b, "top")])

    assert {item["id"] for item in merged} == {1, 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_article_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domains.article'`

- [ ] **Step 3: Implement `app/domains/article.py`**

```python
from datetime import datetime, timezone


def normalize_item(raw_item: dict, source: str) -> dict:
    return {
        "id": raw_item["id"],
        "title": raw_item["title"],
        "url": raw_item.get("url"),
        "author": raw_item.get("by"),
        "score": raw_item.get("score", 0),
        "comment_count": raw_item.get("descendants", 0),
        "item_type": raw_item["type"],
        "sources": [source],
        "posted_at": datetime.fromtimestamp(raw_item["time"], tz=timezone.utc),
    }


def merge_batch(items: list[tuple[dict, str]]) -> list[dict]:
    merged: dict[int, dict] = {}

    for raw_item, source in items:
        normalized = normalize_item(raw_item, source)
        item_id = normalized["id"]

        if item_id not in merged:
            merged[item_id] = normalized
        else:
            existing = merged[item_id]
            existing["sources"] = sorted(set(existing["sources"]) | {source})
            existing["score"] = normalized["score"]
            existing["comment_count"] = normalized["comment_count"]

    return list(merged.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_article_domain.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/domains/article.py tests/test_article_domain.py
git commit -m "feat: article domain normalization and same-batch merge"
```

---

### Task 5: Hacker News API client (async, best-effort)

**Files:**
- Create: `app/network/hn_client.py`
- Test: `tests/test_hn_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `HN_LISTS = ["topstories", "beststories", "askstories", "showstories"]`; `async def fetch_story_ids(client: httpx.AsyncClient, list_name: str) -> list[int]`; `async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None` (returns `None` instead of raising on failure); `async def fetch_all(limit_per_list: int = 30) -> tuple[list[tuple[dict, str]], int]` returns `(items_with_source, failed_count)` — the exact input shape Task 4's `merge_batch` consumes.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_hn_client.py
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.network.hn_client import fetch_all, fetch_item, fetch_story_ids

BASE_URL = "https://hacker-news.firebaseio.com/v0"


def _mock_response(json_data):
    response = httpx.Response(200, json=json_data)
    return response


@pytest.mark.asyncio
async def test_fetch_story_ids_calls_correct_url():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response([1, 2, 3])

    result = await fetch_story_ids(mock_client, "topstories")

    mock_client.get.assert_called_once_with(f"{BASE_URL}/topstories.json")
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_fetch_item_returns_data_on_success():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response({"id": 1, "title": "Test"})

    result = await fetch_item(mock_client, 1)

    assert result == {"id": 1, "title": "Test"}


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_failure():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException("timed out")

    result = await fetch_item(mock_client, 1)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_all_counts_failures_without_aborting_batch():
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def fake_get(url, *args, **kwargs):
        if url.endswith("topstories.json"):
            return _mock_response([1, 2])
        if url.endswith("beststories.json"):
            return _mock_response([2])
        if url.endswith("askstories.json"):
            return _mock_response([])
        if url.endswith("showstories.json"):
            return _mock_response([])
        if url.endswith("/1.json"):
            return _mock_response({"id": 1, "title": "One", "type": "story", "time": 1700000000})
        if url.endswith("/2.json"):
            raise httpx.TimeoutException("timed out")
        raise AssertionError(f"unexpected url {url}")

    mock_client.get.side_effect = fake_get

    # `async with httpx.AsyncClient(...) as client:` needs the patched class,
    # when called, to return something whose __aenter__ resolves to mock_client.
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__.return_value = mock_client
    mock_client_context.__aexit__.return_value = None

    with patch("app.network.hn_client.httpx.AsyncClient", return_value=mock_client_context):
        items_with_source, failed_count = await fetch_all(limit_per_list=2)

    assert failed_count == 2  # item 2 fails once for "top" and once for "best"
    assert len(items_with_source) == 1
    assert items_with_source[0][0]["id"] == 1
```

**Note:** these tests need `pytest-asyncio`; add it now.

- [ ] **Step 2: Add `pytest-asyncio` and enable it**

```toml
# add to pyproject.toml [dependency-groups] dev list:
    "pytest-asyncio>=0.24",
```

```ini
# create pytest.ini
[pytest]
asyncio_mode = auto
```

Run: `uv sync`

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_hn_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.network.hn_client'`

- [ ] **Step 4: Implement `app/network/hn_client.py`**

```python
import asyncio

import httpx

BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_LISTS = ["topstories", "beststories", "askstories", "showstories"]


async def fetch_story_ids(client: httpx.AsyncClient, list_name: str) -> list[int]:
    response = await client.get(f"{BASE_URL}/{list_name}.json")
    response.raise_for_status()
    return response.json()


async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    try:
        response = await client.get(f"{BASE_URL}/item/{item_id}.json")
        response.raise_for_status()
        return response.json()
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError):
        return None


async def fetch_all(limit_per_list: int = 30) -> tuple[list[tuple[dict, str]], int]:
    items_with_source: list[tuple[dict, str]] = []
    failed_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        for list_name in HN_LISTS:
            source = list_name.replace("stories", "")  # "topstories" -> "top"
            ids = (await fetch_story_ids(client, list_name))[:limit_per_list]

            results = await asyncio.gather(*(fetch_item(client, item_id) for item_id in ids))

            for raw_item in results:
                if raw_item is None:
                    failed_count += 1
                else:
                    items_with_source.append((raw_item, source))

    return items_with_source, failed_count
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_hn_client.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
git add app/network/hn_client.py tests/test_hn_client.py pyproject.toml pytest.ini
git commit -m "feat: async hacker news client with best-effort item fetching"
```

---

### Task 6: Repository — upsert and query logic

**Files:**
- Create: `app/database/repository.py`
- Modify: `tests/test_repository.py` (add upsert/query tests alongside the Task 3 round-trip test)

**Interfaces:**
- Consumes: `Article` model, `Session` (Task 3); normalized dicts shaped like `merge_batch`'s output (Task 4).
- Produces: `upsert_articles(session: Session, articles: list[dict]) -> tuple[int, int]` returns `(created_count, updated_count)`; `query_articles(session: Session, keyword: str | None, min_score: int | None, source: str | None, sort: str, page: int, page_size: int) -> list[Article]`.

- [ ] **Step 1: Write the failing upsert tests (append to `tests/test_repository.py`)**

```python
from datetime import datetime, timezone

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
```

- [ ] **Step 2: Run tests to verify they fail**

Note: `tests/test_repository.py` already imports `Article`, `datetime`, and `timezone` at
the top (added in Task 3, for the round-trip test) — the new tests above reuse those same
imports; do not add a second copy.

Run: `uv run pytest tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.database.repository'`

- [ ] **Step 3: Implement `app/database/repository.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database.models import Article


def upsert_articles(session: Session, articles: list[dict]) -> tuple[int, int]:
    if not articles:
        return 0, 0

    existing_ids = {
        row.id
        for row in session.query(Article.id).filter(
            Article.id.in_([a["id"] for a in articles])
        )
    }

    now = datetime.now(timezone.utc)
    rows = [{**article, "fetched_at": now} for article in articles]

    stmt = pg_insert(Article).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "url": stmt.excluded.url,
            "author": stmt.excluded.author,
            "score": stmt.excluded.score,
            "comment_count": stmt.excluded.comment_count,
            "sources": stmt.excluded.sources,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    session.execute(stmt)
    session.commit()

    created = sum(1 for a in articles if a["id"] not in existing_ids)
    updated = len(articles) - created
    return created, updated


def query_articles(
    session: Session,
    keyword: str | None,
    min_score: int | None,
    source: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> list[Article]:
    query = session.query(Article)

    if keyword:
        query = query.filter(Article.title.ilike(f"%{keyword}%"))
    if min_score is not None:
        query = query.filter(Article.score >= min_score)
    if source:
        query = query.filter(Article.sources.any(source))

    if sort == "posted_at_desc":
        query = query.order_by(Article.posted_at.desc())
    else:
        query = query.order_by(Article.score.desc())

    offset = (page - 1) * page_size
    return query.offset(offset).limit(page_size).all()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_repository.py -v`
Expected: PASS (all tests, including the Task 3 round-trip test)

- [ ] **Step 5: Commit**

```bash
git add app/database/repository.py tests/test_repository.py
git commit -m "feat: article upsert and filtered query repository"
```

---

### Task 7: FastAPI routes, app wiring, and error handling

**Files:**
- Create: `app/routes/articles.py`
- Create: `app/main.py`
- Create: `tests/test_articles_routes.py`

**Interfaces:**
- Consumes: `fetch_all` (Task 5), `merge_batch` (Task 4), `upsert_articles`/`query_articles` (Task 6), `get_db`/`Base`/`engine` (Task 3).
- Produces: a running FastAPI `app` object (`app.main:app`) with the three endpoints wired up.

- [ ] **Step 1: Write the failing route tests**

```python
# tests/test_articles_routes.py
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.database.models import Article
from app.database.repository import upsert_articles
from app.database.session import get_db
from app.main import app


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


def test_refresh_upserts_and_reports_failures(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)

    fake_items = [
        ({"id": 10, "title": "New story", "by": "z", "score": 1,
          "descendants": 0, "type": "story", "time": 1700000000}, "top"),
    ]

    with patch("app.routes.articles.fetch_all", new=AsyncMock(return_value=(fake_items, 3))):
        response = client.post("/articles/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body == {"fetched": 1, "created": 1, "updated": 0, "failed": 3}
    assert db_session.get(Article, 10) is not None
    app.dependency_overrides.clear()


def test_unexpected_exception_returns_clean_500(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app, raise_server_exceptions=False)

    with patch("app.routes.articles.query_articles", side_effect=RuntimeError("boom")):
        response = client.get("/articles")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_articles_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Implement `app/routes/articles.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.models import Article
from app.database.repository import query_articles, upsert_articles
from app.database.session import get_db
from app.domains.article import merge_batch
from app.network.hn_client import fetch_all

router = APIRouter()


@router.get("/articles")
def list_articles(
    keyword: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    source: str | None = None,
    sort: str = "score_desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    articles = query_articles(db, keyword, min_score, source, sort, page, page_size)
    return [
        {
            "id": a.id, "title": a.title, "url": a.url, "author": a.author,
            "score": a.score, "comment_count": a.comment_count,
            "item_type": a.item_type, "sources": a.sources,
            "posted_at": a.posted_at.isoformat(),
        }
        for a in articles
    ]


@router.get("/articles/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return {
        "id": article.id, "title": article.title, "url": article.url,
        "author": article.author, "score": article.score,
        "comment_count": article.comment_count, "item_type": article.item_type,
        "sources": article.sources, "posted_at": article.posted_at.isoformat(),
    }


@router.post("/articles/refresh")
async def refresh_articles(db: Session = Depends(get_db)):
    items_with_source, failed = await fetch_all()
    merged = merge_batch(items_with_source)
    created, updated = upsert_articles(db, merged)
    return {"fetched": len(merged), "created": created, "updated": updated, "failed": failed}
```

- [ ] **Step 4: Implement `app/main.py`**

```python
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.database.session import Base, engine
from app.routes import articles

logger = logging.getLogger("hn_capstone")

Base.metadata.create_all(engine)

app = FastAPI(title="Hacker News Backend Aggregator")
app.include_router(articles.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_articles_routes.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests across every task pass together.

- [ ] **Step 7: Commit**

```bash
git add app/routes/articles.py app/main.py tests/test_articles_routes.py
git commit -m "feat: wire up FastAPI routes, dependency injection, and global error handler"
```

---

### Task 8: Manual end-to-end smoke test

**Files:**
- Modify: `README.md` (add a "Verified" note — no code changes)

**Interfaces:**
- Consumes: the running application from Task 7.
- Produces: nothing new — this task is a manual verification pass against the real Hacker News API and the real dev database.

- [ ] **Step 1: Start the app**

Run: `uv run uvicorn app.main:app --reload`
Expected: starts without errors, logs show `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 2: Trigger a real refresh**

Run: `curl -X POST http://127.0.0.1:8000/articles/refresh`
Expected: a JSON object like `{"fetched": 118, "created": 118, "updated": 0, "failed": 0}` (numbers will vary with real HN data).

- [ ] **Step 3: List articles**

Run: `curl "http://127.0.0.1:8000/articles?min_score=100&sort=score_desc"`
Expected: a JSON array of articles with `score >= 100`, highest first.

- [ ] **Step 4: Fetch one article by id, and a missing one**

Run: `curl http://127.0.0.1:8000/articles/<a real id from step 3>` then `curl -i http://127.0.0.1:8000/articles/1`
Expected: the real id returns `200` with article data; id `1` (not a current HN top/best/ask/show story) returns `404`.

- [ ] **Step 5: Re-run refresh to confirm idempotency**

Run: `curl -X POST http://127.0.0.1:8000/articles/refresh` (again)
Expected: `created` is near 0, `updated` reflects the same articles refreshed again — no errors, no duplicate rows (spot-check with `curl http://127.0.0.1:8000/articles?page_size=200` and confirm no repeated ids).

- [ ] **Step 6: Update README and commit**

```markdown
<!-- append to README.md -->

## Verified

Manually smoke-tested end-to-end against the real Hacker News API on 2026-09-30:
refresh, filtered listing, single-article lookup (including 404), and
idempotent re-refresh all behave as designed.
```

```bash
git add README.md
git commit -m "docs: record end-to-end smoke test"
```
