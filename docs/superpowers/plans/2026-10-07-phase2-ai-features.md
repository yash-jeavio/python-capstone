# Phase 2 AI Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three AI endpoints the existing frontend already calls — on-demand article summaries, embedding-based related articles, and retrieval-grounded Q&A — and replace the "coming in Phase 2" placeholder with real unavailable/error states.

**Architecture:** Preserves the Phase 1 four-layer split. `domains/ai.py` stays pure (prompts, truncation, embedding-input assembly). `network/openai_client.py` and `network/content_fetcher.py` own outbound I/O and never touch the database. `database/repository.py` owns all SQL including pgvector similarity search. `routes/ai.py` composes them. Summaries are generated per-article on demand and cached forever; embeddings are backfilled corpus-wide on first use of either corpus endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL + pgvector, Alembic, OpenAI (`gpt-4o-mini`, `text-embedding-3-small`), trafilatura, httpx, pytest; React 18 + TanStack Query + Vitest on the frontend.

**Spec:** `docs/superpowers/specs/2026-10-07-phase2-ai-features-design.md`

## Global Constraints

- **Generation model:** `gpt-4o-mini`. **Embedding model:** `text-embedding-3-small`, **1536 dimensions**.
- **Endpoint paths are fixed by the shipped frontend contract and must not drift:** `GET /articles/{id}/summary`, `GET /articles/{id}/related`, `POST /chat/ask`.
- **Content truncation limit:** 12,000 characters, defined once as `MAX_CONTENT_CHARS` in `app/domains/ai.py`.
- **Comment fallback size:** top 10 top-level HN comments, in HN's own `kids` ordering.
- **Retrieval size:** 5 articles for both `/related` and `/chat/ask`.
- **Status codes:** `404` article not found; `501` `openai_api_key` unset; `503` OpenAI failure or total content-retrieval failure; `500` unforeseen (existing handler).
- **No test may call the OpenAI API or fetch a live web page.** All outbound clients are injected and mocked.
- **Layering:** `domains/` has no I/O and no DB imports; `network/` has no DB imports; all SQL lives in `database/repository.py`.
- **Schema ownership:** Alembic owns dev/prod schema; `tests/conftest.py` keeps `create_all`/`drop_all`.
- **Python floor:** `>=3.11` (unchanged from `pyproject.toml`).
- **Embedding input:** title + summary when a summary exists, title alone otherwise. Never the scraped page text.

## Review Focus

These five input classes are implied by the spec but easy to leave untested. Each has a test assigned to the task that owns the code.

1. **Article with `url IS NULL`** (Ask HN / text posts, a real fraction of the corpus) — `/summary` must go straight to the comment fallback without attempting a fetch. *Test in Task 11.*
2. **Backfill with nothing to embed** — `ensure_embeddings` must short-circuit and never send an empty `input` array to OpenAI, which is an API error. *Test in Task 10.*
3. **`/related` on a corpus smaller than the retrieval size** — must return what exists, never error, and never include the article itself. *Test in Task 9.*
4. **Blank or whitespace-only question to `/chat/ask`** — must be rejected before an empty string reaches the embedding API. *Test in Task 12.*
5. **Repeat `/summary` request for an already-summarized article** — must make **zero** OpenAI calls. This is the entire cost-control mechanism, so a regression here is a billing bug, not a correctness one. *Test in Task 11.*

---

### Task 1: Introduce Alembic

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/<rev>_baseline.py`
- Modify: `pyproject.toml`, `app/main.py:14-22`, `Dockerfile:6`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes: `app.database.session.Base`, `app.common.config.get_settings`.
- Produces: a working `alembic upgrade head`; `app.main.run_migrations()` called from `lifespan`.

- [ ] **Step 1: Add the dependency**

```bash
uv add alembic
```

- [ ] **Step 2: Initialise the migration tree**

```bash
uv run alembic init alembic
```

- [ ] **Step 3: Point Alembic at our settings and metadata**

Replace the `config.set_main_option` / `target_metadata` region of `alembic/env.py` so it reads the URL from our settings instead of `alembic.ini`:

```python
# alembic/env.py — after `config = context.config`
from app.common.config import get_settings
from app.database.session import Base
import app.database.models  # noqa: F401 — import for side effect: registers Article on Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```

- [ ] **Step 4: Generate the baseline migration**

Bring the dev database up first (`docker compose up -d db`), then:

```bash
uv run alembic revision --autogenerate -m "baseline: articles table"
```

Open the generated file in `alembic/versions/` and confirm it creates the `articles` table with all ten Phase 1 columns (`id`, `title`, `url`, `author`, `score`, `comment_count`, `item_type`, `sources`, `posted_at`, `fetched_at`). Autogenerate compares against the live database — if your dev DB already has the table, the migration will come out **empty**, in which case write the `create_table` by hand to match `app/database/models.py`.

- [ ] **Step 5: Stamp the existing database**

Your dev database already contains the `articles` table and ~295 rows, so the baseline must be marked as applied without running:

```bash
uv run alembic stamp head
```

Expected: `Running stamp_revision -> <rev>`. A fresh clone with no volume skips this — `upgrade head` creates the table normally.

- [ ] **Step 6: Write the failing test**

```python
# tests/test_migrations.py
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_head_revision():
    # Multiple heads mean someone branched migrations without merging; alembic
    # upgrade head then fails at runtime rather than at review time.
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(script.get_heads()) == 1


def test_baseline_creates_articles_table():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.walk_revisions())
    source = open(revisions[-1].path).read()
    assert "articles" in source
    assert "create_table" in source
```

- [ ] **Step 7: Run it to confirm it passes**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: both PASS. (This test guards structure, so it passes as soon as Step 4 is correct.)

- [ ] **Step 8: Replace `create_all` with `upgrade head` in lifespan**

In `app/main.py`, delete the `Base.metadata.create_all(engine)` line and add:

```python
from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    # Alembic owns dev/prod schema; tests keep create_all (see conftest).
    command.upgrade(Config("alembic.ini"), "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    with SessionLocal() as db:
        await articles.seed_if_empty(db)
    yield
```

Remove the now-unused `Base` from the `app.database.session` import.

- [ ] **Step 9: Copy the migration tree into the image**

`alembic.ini` and `alembic/` must exist in the container or `upgrade head` fails at startup. In `Dockerfile`, after `COPY app ./app`:

```dockerfile
COPY alembic.ini ./
COPY alembic ./alembic
```

- [ ] **Step 10: Verify the app still boots and the suite passes**

Run: `uv run pytest -q` then `uv run uvicorn app.main:app`
Expected: 43 passed; uvicorn starts with no migration error and logs no schema changes.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock alembic.ini alembic tests/test_migrations.py app/main.py Dockerfile
git commit -m "feat: introduce Alembic for schema migrations"
```

---

### Task 2: pgvector and the three new columns

**Files:**
- Modify: `pyproject.toml`, `app/database/models.py:10-24`, `tests/conftest.py:7-17`, `docker-compose.yml:2-3,19-20`
- Create: `alembic/versions/<rev>_add_ai_columns.py`
- Test: `tests/test_models_ai_columns.py`

**Interfaces:**
- Consumes: Task 1's Alembic setup.
- Produces: `Article.summary: str | None`, `Article.summary_generated_at: datetime | None`, `Article.embedding: list[float] | None` (`Vector(1536)`).

- [ ] **Step 1: Add the dependency**

```bash
uv add pgvector
```

- [ ] **Step 2: Swap both Postgres images**

In `docker-compose.yml`, change the image for **both** `db` and `test-db` from `postgres:16` to:

```yaml
    image: pgvector/pgvector:pg16
```

`test-db` matters as much as `db` — `conftest.py` runs `create_all` against it and a `Vector` column cannot be created without the extension. The image is built on Postgres 16, so your existing `hn_db_data` volume stays readable.

- [ ] **Step 3: Recreate the containers**

```bash
docker compose up -d --force-recreate db test-db
```

Expected: both healthy. Confirm your data survived: `docker compose exec db psql -U hn_user -d hn_capstone -c "select count(*) from articles;"` should still report 295.

- [ ] **Step 4: Write the failing test**

```python
# tests/test_models_ai_columns.py
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
```

- [ ] **Step 5: Run it to verify it fails**

Run: `uv run pytest tests/test_models_ai_columns.py -v`
Expected: FAIL — `TypeError: 'summary' is an invalid keyword argument` or `AttributeError`.

- [ ] **Step 6: Create the extension in the test fixture**

The `vector` extension is per-database, so the test database needs it before `create_all`. In `tests/conftest.py`:

```python
import pytest
from sqlalchemy import text

from app.common.config import get_settings
from app.database.session import Base, engine_for, session_factory_for


@pytest.fixture
def db_session():
    engine = engine_for(get_settings().test_database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    session_factory = session_factory_for(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
```

- [ ] **Step 7: Add the columns to the model**

In `app/database/models.py`:

```python
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[int] = mapped_column(default=0)
    comment_count: Mapped[int] = mapped_column(default=0)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    sources: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 1536 dims is fixed by text-embedding-3-small. NULL is the backfill target.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run pytest tests/test_models_ai_columns.py -v`
Expected: both PASS.

- [ ] **Step 9: Generate the migration**

```bash
uv run alembic revision --autogenerate -m "add summary and embedding columns"
```

Then **edit the generated file** — autogenerate will not emit the extension statement, and `op.add_column` with a `Vector` type fails without it. The upgrade must read:

```python
import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("articles", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "articles", sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "articles", sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("articles", "embedding")
    op.drop_column("articles", "summary_generated_at")
    op.drop_column("articles", "summary")
    # The extension is left in place: other objects may depend on it.
```

- [ ] **Step 10: Apply it and verify**

```bash
uv run alembic upgrade head
docker compose exec db psql -U hn_user -d hn_capstone -c "\d articles"
```

Expected: `summary`, `summary_generated_at`, and `embedding vector(1536)` all listed, and the existing 295 rows intact.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock app/database/models.py tests/conftest.py tests/test_models_ai_columns.py docker-compose.yml alembic/versions
git commit -m "feat: add pgvector and AI columns to articles"
```

---

### Task 3: AI configuration settings

**Files:**
- Modify: `app/common/config.py`, `.env.example`, `.env`, `docker-compose.yml:24-27`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.openai_api_key: str | None`, `Settings.openai_model: str`, `Settings.embedding_model: str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_ai_settings_have_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    # Absence of a key is the 501 path, not a startup crash.
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.embedding_model == "text-embedding-3-small"


def test_openai_api_key_is_read_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key == "sk-test-123"
```

Add `from app.common.config import Settings` to the imports if it is not already there.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'openai_api_key'`.

- [ ] **Step 3: Add the settings**

```python
class Settings(BaseSettings):
    database_url: str
    test_database_url: str
    # Optional: a clone with no key runs fine and reports AI as unconfigured (501).
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Document and wire the key through**

Append to both `.env.example` and `.env` (in `.env`, use your real key):

```
OPENAI_API_KEY=
```

In `docker-compose.yml`, add to the `backend` service's `environment` block:

```yaml
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
```

The `:-` default keeps `docker compose up` working when the host has no key set.

- [ ] **Step 6: Commit**

```bash
git add app/common/config.py tests/test_config.py .env.example docker-compose.yml
git commit -m "feat: add OpenAI configuration settings"
```

---

### Task 4: Shared article serializer

**Files:**
- Create: `app/routes/serializers.py`
- Modify: `app/routes/articles.py:41-77`
- Test: `tests/test_serializers.py`

**Interfaces:**
- Produces: `serialize_article(article: Article) -> dict` — the single definition of the article JSON shape, used by `/articles`, `/articles/{id}`, `/articles/{id}/related`, and `/chat/ask`'s `sources`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_serializers.py
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_serializers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routes.serializers'`.

- [ ] **Step 3: Write the implementation**

```python
# app/routes/serializers.py
from app.database.models import Article


def serialize_article(article: Article) -> dict:
    """The one definition of the article JSON shape returned by the API.

    Matches the `Article` interface in frontend/src/types/article.ts. Internal
    columns (fetched_at, summary, embedding) are deliberately excluded.
    """
    return {
        "id": article.id,
        "title": article.title,
        "url": article.url,
        "author": article.author,
        "score": article.score,
        "comment_count": article.comment_count,
        "item_type": article.item_type,
        "sources": article.sources,
        "posted_at": article.posted_at.isoformat(),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_serializers.py -v`
Expected: both PASS.

- [ ] **Step 5: Route the existing endpoints through it**

In `app/routes/articles.py`, add `from app.routes.serializers import serialize_article` and replace both hand-built dicts:

```python
@router.get("/articles")
def list_articles(
    keyword: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    source: Literal["top", "best", "ask", "show"] | None = None,
    sort: Literal["score_desc", "posted_at_desc"] = "score_desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    articles = query_articles(db, keyword, min_score, source, sort, page, page_size)
    return [serialize_article(a) for a in articles]


@router.get("/articles/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return serialize_article(article)
```

- [ ] **Step 6: Verify nothing regressed**

Run: `uv run pytest -q`
Expected: all pass — the existing `tests/test_articles_routes.py` assertions on response shape are the regression guard here.

- [ ] **Step 7: Commit**

```bash
git add app/routes/serializers.py app/routes/articles.py tests/test_serializers.py
git commit -m "refactor: extract shared article serializer"
```

---

### Task 5: Domain layer — prompts, truncation, embedding input

**Files:**
- Create: `app/domains/ai.py`
- Test: `tests/test_ai_domain.py`

**Interfaces:**
- Produces:
  - `MAX_CONTENT_CHARS: int = 12_000`
  - `build_embedding_input(title: str, summary: str | None) -> str`
  - `truncate_content(text: str) -> str`
  - `build_summary_messages(title: str, content: str) -> list[dict]`
  - `build_chat_messages(question: str, articles: list[Article]) -> list[dict]`
- Consumes: nothing. Pure functions, no I/O, no DB session. Reads attributes off `Article` instances only.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai_domain.py
from datetime import datetime, timezone

import pytest

from app.database.models import Article
from app.domains.ai import (
    MAX_CONTENT_CHARS,
    build_chat_messages,
    build_embedding_input,
    build_summary_messages,
    truncate_content,
)


def _article(id: int, title: str, summary: str | None = None, score: int = 10) -> Article:
    return Article(
        id=id, title=title, url=f"https://example.com/{id}", author="alice",
        score=score, comment_count=3, item_type="story", sources=["top"],
        posted_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        summary=summary,
    )


def test_embedding_input_is_title_alone_when_no_summary():
    assert build_embedding_input("Rust is fast", None) == "Rust is fast"


def test_embedding_input_combines_title_and_summary():
    result = build_embedding_input("Rust is fast", "A post about Rust performance.")
    assert "Rust is fast" in result
    assert "A post about Rust performance." in result


def test_embedding_input_treats_blank_summary_as_absent():
    # A model that returns whitespace must not pollute the vector with padding.
    assert build_embedding_input("Rust is fast", "   ") == "Rust is fast"


def test_truncate_leaves_short_content_untouched():
    assert truncate_content("short text") == "short text"


def test_truncate_caps_long_content():
    result = truncate_content("word " * 10_000)
    assert len(result) <= MAX_CONTENT_CHARS


def test_truncate_cuts_at_a_whitespace_boundary():
    # Splitting mid-word wastes a token and reads as corruption to the model.
    result = truncate_content("a" * 50 + " " + "b" * MAX_CONTENT_CHARS)
    assert not result.endswith("b")


def test_summary_messages_include_title_and_content():
    messages = build_summary_messages("Rust is fast", "Some article body.")

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Rust is fast" in messages[1]["content"]
    assert "Some article body." in messages[1]["content"]


def test_chat_messages_ground_the_answer_in_the_given_articles():
    articles = [_article(1, "Rust is fast", "About Rust."), _article(2, "Go is simple")]

    messages = build_chat_messages("Which language is faster?", articles)

    prompt = messages[1]["content"]
    assert "Which language is faster?" in prompt
    assert "Rust is fast" in prompt
    assert "Go is simple" in prompt
    # The system prompt must forbid answering outside the retrieved set.
    assert "only" in messages[0]["content"].lower()


def test_chat_messages_handle_an_empty_retrieval_set():
    messages = build_chat_messages("Anything?", [])
    assert "Anything?" in messages[1]["content"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai_domain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domains.ai'`.

- [ ] **Step 3: Write the implementation**

```python
# app/domains/ai.py
"""Pure AI helpers: prompt construction, truncation, embedding input.

No I/O and no database access -- everything here is a deterministic function of
its arguments, so it is tested without mocks.
"""

from app.database.models import Article

# Bounds worst-case cost per summary and stays well inside gpt-4o-mini's context
# window. ~12k chars is roughly 3k tokens. Single source of truth for the limit.
MAX_CONTENT_CHARS = 12_000

SUMMARY_SYSTEM_PROMPT = (
    "You summarize technical articles and discussions from Hacker News. "
    "Write three to four sentences of plain prose. State what the content "
    "actually says; do not speculate beyond it and do not add a preamble."
)

CHAT_SYSTEM_PROMPT = (
    "You answer questions about a collection of Hacker News articles. "
    "Use only the articles provided in the user message. If they do not "
    "contain the answer, say so plainly rather than guessing. Refer to "
    "articles by their titles."
)


def build_embedding_input(title: str, summary: str | None) -> str:
    """Text to embed for an article: title alone, or title plus summary."""
    if summary and summary.strip():
        return f"{title}\n\n{summary.strip()}"
    return title


def truncate_content(text: str) -> str:
    """Cap content at MAX_CONTENT_CHARS, cutting at a whitespace boundary."""
    if len(text) <= MAX_CONTENT_CHARS:
        return text
    cut = text[:MAX_CONTENT_CHARS]
    boundary = cut.rfind(" ")
    # A single unbroken token longer than the limit has no boundary to cut at,
    # so fall back to the hard slice rather than returning an empty string.
    return cut[:boundary] if boundary > 0 else cut


def build_summary_messages(title: str, content: str) -> list[dict]:
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Title: {title}\n\nContent:\n{content}"},
    ]


def build_chat_messages(question: str, articles: list[Article]) -> list[dict]:
    if articles:
        blocks = []
        for article in articles:
            lines = [f"Title: {article.title}", f"Score: {article.score}"]
            if article.url:
                lines.append(f"URL: {article.url}")
            if article.summary:
                lines.append(f"Summary: {article.summary}")
            blocks.append("\n".join(lines))
        context = "\n\n---\n\n".join(blocks)
    else:
        context = "(no articles matched this question)"

    return [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Articles:\n\n{context}\n\nQuestion: {question}"},
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai_domain.py -v`
Expected: all 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domains/ai.py tests/test_ai_domain.py
git commit -m "feat: add pure AI domain helpers"
```

---

### Task 6: OpenAI client

**Files:**
- Create: `app/network/openai_client.py`
- Modify: `pyproject.toml`, `app/main.py`
- Test: `tests/test_openai_client.py`

**Interfaces:**
- Produces:
  - `class AiServiceError(Exception)` — raised on any OpenAI failure; mapped to `503`.
  - `async embed_texts(client, texts: list[str], model: str) -> list[list[float]]`
  - `async complete(client, messages: list[dict], model: str) -> str`
  - `get_openai_client() -> AsyncOpenAI | None` — FastAPI dependency; `None` when no key is configured.
- Consumes: `app.common.config.get_settings`.

- [ ] **Step 1: Add the dependency**

```bash
uv add openai
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_openai_client.py
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APITimeoutError

from app.network.openai_client import (
    AiServiceError,
    complete,
    embed_texts,
    get_openai_client,
)


def _embedding_response(vectors):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


def _chat_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


# A plain AsyncMock is used rather than AsyncMock(spec=AsyncOpenAI): the SDK
# exposes calls through nested resource attributes (client.embeddings.create),
# which spec'ing does not reproduce usefully.


async def test_embed_texts_returns_vectors_in_order():
    client = AsyncMock()
    client.embeddings.create.return_value = _embedding_response([[0.1, 0.2], [0.3, 0.4]])

    result = await embed_texts(client, ["a", "b"], "text-embedding-3-small")

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    client.embeddings.create.assert_awaited_once_with(
        model="text-embedding-3-small", input=["a", "b"]
    )


async def test_embed_texts_short_circuits_on_empty_input():
    # OpenAI rejects an empty input array, so this must never reach the API.
    client = AsyncMock()

    result = await embed_texts(client, [], "text-embedding-3-small")

    assert result == []
    client.embeddings.create.assert_not_awaited()


async def test_embed_texts_raises_when_the_api_returns_fewer_vectors():
    # Silent zip() truncation would leave articles with a NULL embedding and an
    # endless backfill loop, so a count mismatch must be loud.
    client = AsyncMock()
    client.embeddings.create.return_value = _embedding_response([[0.1, 0.2]])

    with pytest.raises(AiServiceError):
        await embed_texts(client, ["a", "b"], "text-embedding-3-small")


async def test_embed_texts_wraps_api_errors():
    client = AsyncMock()
    client.embeddings.create.side_effect = APITimeoutError(request=None)

    with pytest.raises(AiServiceError):
        await embed_texts(client, ["a"], "text-embedding-3-small")


async def test_complete_returns_the_message_text():
    client = AsyncMock()
    client.chat.completions.create.return_value = _chat_response("A summary.")

    result = await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")

    assert result == "A summary."


async def test_complete_wraps_api_errors():
    client = AsyncMock()
    client.chat.completions.create.side_effect = APITimeoutError(request=None)

    with pytest.raises(AiServiceError):
        await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")


async def test_complete_raises_on_an_empty_response():
    client = AsyncMock()
    client.chat.completions.create.return_value = _chat_response(None)

    with pytest.raises(AiServiceError):
        await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")


def test_get_openai_client_returns_none_without_a_key(monkeypatch):
    monkeypatch.setattr(
        "app.network.openai_client.get_settings",
        lambda: SimpleNamespace(openai_api_key=None),
    )
    assert get_openai_client() is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_openai_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.network.openai_client'`.

- [ ] **Step 4: Write the implementation**

```python
# app/network/openai_client.py
import logging

from openai import AsyncOpenAI, OpenAIError

from app.common.config import get_settings

logger = logging.getLogger("hn_capstone")


class AiServiceError(Exception):
    """An OpenAI call failed. Mapped to HTTP 503 -- transient, retry may work."""


def get_openai_client() -> AsyncOpenAI | None:
    """FastAPI dependency. Returns None when no API key is configured, which
    routes translate to 501 (not configured) rather than a failure."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_texts(client: AsyncOpenAI, texts: list[str], model: str) -> list[list[float]]:
    # OpenAI rejects an empty input array; a no-op backfill must not call out.
    if not texts:
        return []
    try:
        response = await client.embeddings.create(model=model, input=texts)
    except OpenAIError as exc:
        logger.warning("Embedding call failed: %s", exc)
        raise AiServiceError("embedding request failed") from exc

    vectors = [item.embedding for item in response.data]
    if len(vectors) != len(texts):
        # Pairing by zip() would silently drop articles and leave them NULL.
        raise AiServiceError(
            f"expected {len(texts)} embeddings, received {len(vectors)}"
        )
    return vectors


async def complete(client: AsyncOpenAI, messages: list[dict], model: str) -> str:
    try:
        response = await client.chat.completions.create(model=model, messages=messages)
    except OpenAIError as exc:
        logger.warning("Completion call failed: %s", exc)
        raise AiServiceError("completion request failed") from exc

    content = response.choices[0].message.content
    if not content:
        raise AiServiceError("completion returned no content")
    return content
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_openai_client.py -v`
Expected: all 8 PASS.

- [ ] **Step 6: Map the error to 503**

In `app/main.py`, add an exception handler above the catch-all. Starlette resolves handlers by walking the exception's MRO, so the specific one wins over `Exception`:

```python
from app.network.openai_client import AiServiceError


@app.exception_handler(AiServiceError)
async def ai_service_error_handler(request: Request, exc: AiServiceError):
    logger.warning("AI service unavailable on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=503, content={"detail": "AI service temporarily unavailable"}
    )
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock app/network/openai_client.py app/main.py tests/test_openai_client.py
git commit -m "feat: add OpenAI client with 503 error mapping"
```

---

### Task 7: Content fetcher

**Files:**
- Create: `app/network/content_fetcher.py`
- Modify: `pyproject.toml`
- Test: `tests/test_content_fetcher.py`

**Interfaces:**
- Produces: `async fetch_article_text(client: httpx.AsyncClient, url: str) -> str | None` — `None` signals "fall back to comments", never raises.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Add the dependency**

```bash
uv add trafilatura
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_content_fetcher.py
from unittest.mock import AsyncMock

import httpx

from app.network.content_fetcher import fetch_article_text

ARTICLE_HTML = """
<html><body>
<nav>Home About Contact</nav>
<article><p>Rust achieves memory safety without a garbage collector.
It does this through an ownership system checked at compile time.</p></article>
<footer>Copyright 2026</footer>
</body></html>
"""


def _response(status=200, text="", content_type="text/html", url="https://example.com"):
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("GET", url),
    )


async def test_extracts_readable_text_and_drops_chrome():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text=ARTICLE_HTML)

    result = await fetch_article_text(client, "https://example.com/rust")

    assert "memory safety" in result
    assert "Home About Contact" not in result


async def test_follows_redirects():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text=ARTICLE_HTML)

    await fetch_article_text(client, "https://example.com/rust")

    assert client.get.await_args.kwargs["follow_redirects"] is True


async def test_returns_none_on_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status=404, text="Not found")

    assert await fetch_article_text(client, "https://example.com/gone") is None


async def test_returns_none_on_timeout():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ReadTimeout("too slow")

    assert await fetch_article_text(client, "https://example.com/slow") is None


async def test_returns_none_for_non_html_content():
    # HN links to PDFs and images regularly; trafilatura cannot read them.
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text="%PDF-1.7", content_type="application/pdf")

    assert await fetch_article_text(client, "https://example.com/paper.pdf") is None


async def test_returns_none_when_nothing_extractable():
    # A JS-only shell or a paywall yields markup with no article body.
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text="<html><body><div id='root'></div></body></html>")

    assert await fetch_article_text(client, "https://example.com/spa") is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_content_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.network.content_fetcher'`.

- [ ] **Step 4: Write the implementation**

```python
# app/network/content_fetcher.py
import logging

import httpx
import trafilatura

logger = logging.getLogger("hn_capstone")


async def fetch_article_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a URL and extract its readable body text.

    Returns None for every failure mode -- unreachable host, non-2xx, non-HTML
    body, or markup with no extractable article. None is the caller's signal to
    fall back to the HN comment thread, so this never raises.
    """
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("Content fetch failed for %s: %s", url, exc)
        return None

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        logger.info("Skipping non-HTML content at %s (%s)", url, content_type)
        return None

    extracted = trafilatura.extract(response.text)
    if not extracted or not extracted.strip():
        logger.info("No extractable article body at %s", url)
        return None
    return extracted.strip()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_content_fetcher.py -v`
Expected: all 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/network/content_fetcher.py tests/test_content_fetcher.py
git commit -m "feat: add article content fetcher with readable-text extraction"
```

---

### Task 8: HN comment fetching

**Files:**
- Modify: `app/network/hn_client.py`
- Test: `tests/test_hn_client.py`

**Interfaces:**
- Produces: `async fetch_comments(client: httpx.AsyncClient, item_id: int, limit: int = 10) -> list[str]`
- Consumes: the existing `fetch_item` in the same module.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hn_client.py`:

```python
from app.network.hn_client import fetch_comments


async def test_fetch_comments_returns_top_level_comment_text():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": [10, 11]}),
        _mock_response({"id": 10, "text": "First comment"}),
        _mock_response({"id": 11, "text": "Second comment"}),
    ]

    result = await fetch_comments(mock_client, 1)

    assert result == ["First comment", "Second comment"]


async def test_fetch_comments_respects_the_limit():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": list(range(100, 130))}),
        *[_mock_response({"id": i, "text": f"c{i}"}) for i in range(100, 110)],
    ]

    result = await fetch_comments(mock_client, 1, limit=10)

    assert len(result) == 10


async def test_fetch_comments_skips_deleted_dead_and_textless():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": [10, 11, 12, 13]}),
        _mock_response({"id": 10, "text": "Good"}),
        _mock_response({"id": 11, "deleted": True}),
        _mock_response({"id": 12, "dead": True, "text": "Spam"}),
        _mock_response({"id": 13, "id": 13}),
    ]

    result = await fetch_comments(mock_client, 1)

    assert result == ["Good"]


async def test_fetch_comments_returns_empty_when_story_has_no_kids():
    # Ask HN posts with no replies, and any story nobody has commented on.
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response({"id": 1, "title": "Lonely"})

    assert await fetch_comments(mock_client, 1) == []


async def test_fetch_comments_returns_empty_when_the_story_fetch_fails():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ReadTimeout("too slow")

    assert await fetch_comments(mock_client, 1) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_hn_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_comments'`.

- [ ] **Step 3: Write the implementation**

Append to `app/network/hn_client.py`:

```python
async def fetch_comments(
    client: httpx.AsyncClient, item_id: int, limit: int = 10
) -> list[str]:
    """Top-level comment bodies for a story, in HN's own `kids` ordering.

    Used as the summarization fallback when a story has no URL (Ask HN, text
    posts) or its linked page cannot be fetched. Best-effort like fetch_item:
    an unreachable story or comment yields fewer results, never an exception.
    """
    story = await fetch_item(client, item_id)
    if story is None:
        return []

    kid_ids = (story.get("kids") or [])[:limit]
    if not kid_ids:
        return []

    comments = await asyncio.gather(*(fetch_item(client, kid) for kid in kid_ids))
    return [
        comment["text"]
        for comment in comments
        if comment
        and not comment.get("deleted")
        and not comment.get("dead")
        and comment.get("text")
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_hn_client.py -v`
Expected: all PASS, including the pre-existing tests.

- [ ] **Step 5: Commit**

```bash
git add app/network/hn_client.py tests/test_hn_client.py
git commit -m "feat: fetch top-level HN comments for summarization fallback"
```

---

### Task 9: Repository — embedding and summary queries

**Files:**
- Modify: `app/database/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Produces:
  - `articles_missing_embeddings(session) -> list[Article]`
  - `store_embeddings(session, pairs: list[tuple[Article, list[float]]]) -> None`
  - `store_summary(session, article: Article, summary: str, embedding: list[float]) -> None`
  - `find_similar(session, embedding: list[float], limit: int = 5, exclude_id: int | None = None) -> list[Article]`
- Consumes: `Article` from Task 2 (with `summary`, `summary_generated_at`, `embedding`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_repository.py`. Add the imports `from app.database.repository import articles_missing_embeddings, find_similar, store_embeddings, store_summary` and, if not already present, `from datetime import datetime, timezone`.

```python
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
```

Add `import pytest` at the top of the file if it is not already imported.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'articles_missing_embeddings'`.

- [ ] **Step 3: Write the implementation**

Append to `app/database/repository.py`:

```python
def articles_missing_embeddings(session: Session) -> list[Article]:
    """Articles with no vector yet -- the backfill target."""
    return session.query(Article).filter(Article.embedding.is_(None)).all()


def store_embeddings(
    session: Session, pairs: list[tuple[Article, list[float]]]
) -> None:
    """Attach vectors to articles in one transaction."""
    for article, embedding in pairs:
        article.embedding = embedding
    session.commit()


def store_summary(
    session: Session, article: Article, summary: str, embedding: list[float]
) -> None:
    """Write a summary and its refreshed vector together.

    One transaction on purpose: the vector is derived from title + summary, so a
    committed summary paired with a stale vector would be an inconsistent state
    that nothing later repairs (the backfill only looks for NULL embeddings).
    """
    article.summary = summary
    article.summary_generated_at = datetime.now(timezone.utc)
    article.embedding = embedding
    session.commit()


def find_similar(
    session: Session,
    embedding: list[float],
    limit: int = 5,
    exclude_id: int | None = None,
) -> list[Article]:
    """Nearest articles by cosine distance, computed in Postgres by pgvector."""
    query = session.query(Article).filter(Article.embedding.is_not(None))
    if exclude_id is not None:
        query = query.filter(Article.id != exclude_id)
    return (
        query.order_by(Article.embedding.cosine_distance(embedding)).limit(limit).all()
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_repository.py -v`
Expected: all PASS, including the pre-existing upsert and query tests.

- [ ] **Step 5: Commit**

```bash
git add app/database/repository.py tests/test_repository.py
git commit -m "feat: add embedding and summary repository queries"
```

---

### Task 10: Backfill and the `/related` endpoint

**Files:**
- Create: `app/routes/ai.py`
- Modify: `app/main.py`
- Test: `tests/test_ai_routes.py`

**Interfaces:**
- Produces:
  - `async ensure_embeddings(db, client, settings) -> None` — idempotent corpus backfill.
  - `GET /articles/{article_id}/related` → `{"related": [article, ...]}`
- Consumes: `articles_missing_embeddings`, `store_embeddings`, `find_similar` (Task 9); `embed_texts`, `get_openai_client`, `AiServiceError` (Task 6); `build_embedding_input` (Task 5); `serialize_article` (Task 4).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai_routes.py
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


@pytest.fixture
def client(db_session):
    """TestClient with the DB and OpenAI client overridden.

    `mock` is attached to the client so tests can assert on API calls.
    """
    mock_openai = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_openai_client] = lambda: mock_openai
    test_client = TestClient(app)
    test_client.mock = mock_openai
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unconfigured_client(db_session):
    """TestClient simulating no OPENAI_API_KEY."""
    app.dependency_overrides[get_db] = lambda: db_session
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai_routes.py -v`
Expected: FAIL — 404 on every route, because `routes/ai.py` does not exist yet.

- [ ] **Step 3: Write the implementation**

```python
# app/routes/ai.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.database.models import Article
from app.database.repository import (
    articles_missing_embeddings,
    find_similar,
    store_embeddings,
)
from app.database.session import get_db
from app.domains.ai import build_embedding_input
from app.network.openai_client import embed_texts, get_openai_client
from app.routes.serializers import serialize_article

logger = logging.getLogger("hn_capstone")

RETRIEVAL_LIMIT = 5

router = APIRouter()


def require_client(client: AsyncOpenAI | None) -> AsyncOpenAI:
    """501, not 5xx: no key is an expected configuration state, not a fault."""
    if client is None:
        raise HTTPException(status_code=501, detail="AI features are not configured")
    return client


async def ensure_embeddings(
    db: Session, client: AsyncOpenAI, settings: Settings
) -> None:
    """Embed every article that has no vector yet, in one batched call.

    Idempotent and shared by both corpus endpoints. On a fresh database the
    first call embeds the whole corpus; afterwards it covers only what the most
    recent refresh added, and is a no-op when nothing is missing.
    """
    pending = articles_missing_embeddings(db)
    if not pending:
        return

    texts = [build_embedding_input(a.title, a.summary) for a in pending]
    vectors = await embed_texts(client, texts, settings.embedding_model)
    store_embeddings(db, list(zip(pending, vectors)))
    logger.info("Backfilled %d embeddings", len(pending))


@router.get("/articles/{article_id}/related")
async def get_related(
    article_id: int,
    db: Session = Depends(get_db),
    client: AsyncOpenAI | None = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    openai = require_client(client)
    await ensure_embeddings(db, openai, settings)

    related = find_similar(
        db, article.embedding, limit=RETRIEVAL_LIMIT, exclude_id=article.id
    )
    return {"related": [serialize_article(a) for a in related]}
```

- [ ] **Step 4: Register the router**

In `app/main.py`, import and include it alongside the existing one:

```python
from app.routes import ai, articles

app.include_router(articles.router)
app.include_router(ai.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai_routes.py -v`
Expected: all 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/ai.py app/main.py tests/test_ai_routes.py
git commit -m "feat: add embedding backfill and related-articles endpoint"
```

---

### Task 11: The `/summary` endpoint

**Files:**
- Modify: `app/routes/ai.py`
- Test: `tests/test_ai_routes.py`

**Interfaces:**
- Produces: `GET /articles/{article_id}/summary` → `{"summary": str}`
- Consumes: `fetch_article_text` (Task 7), `fetch_comments` (Task 8), `store_summary` (Task 9), `complete`/`embed_texts` (Task 6), `build_summary_messages`/`truncate_content`/`build_embedding_input` (Task 5).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai_routes.py`. Add `from unittest.mock import patch` to the imports, and this helper next to `_embedding_response`:

```python
def _chat_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
```

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai_routes.py -v`
Expected: the ten new tests FAIL with 404 (route not defined); the Task 10 tests still pass.

- [ ] **Step 3: Write the implementation**

Add to `app/routes/ai.py` — extend the imports, then add the route:

```python
import httpx

from app.database.repository import store_summary
from app.domains.ai import build_summary_messages, truncate_content
from app.network.content_fetcher import fetch_article_text
from app.network.hn_client import fetch_comments
from app.network.openai_client import complete

CONTENT_TIMEOUT_SECONDS = 10


async def _acquire_content(article: Article) -> str | None:
    """Page text when there is a fetchable URL, otherwise the HN discussion.

    Returns None only when both paths yield nothing, which the caller maps to 503.
    """
    async with httpx.AsyncClient(timeout=CONTENT_TIMEOUT_SECONDS) as http_client:
        if article.url:
            page_text = await fetch_article_text(http_client, article.url)
            if page_text:
                return page_text
        comments = await fetch_comments(http_client, article.id)

    joined = "\n\n".join(comments).strip()
    return joined or None


@router.get("/articles/{article_id}/summary")
async def get_summary(
    article_id: int,
    db: Session = Depends(get_db),
    client: AsyncOpenAI | None = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Cache check precedes the key check on purpose: an already-summarized
    # article keeps working even if the API key is later removed.
    if article.summary is not None:
        return {"summary": article.summary}

    openai = require_client(client)

    content = await _acquire_content(article)
    if content is None:
        logger.info("No content available to summarize article %d", article.id)
        raise HTTPException(
            status_code=503, detail="Could not retrieve content to summarize"
        )

    messages = build_summary_messages(article.title, truncate_content(content))
    summary = await complete(openai, messages, settings.openai_model)

    # Re-embed from title + summary so the vector matches the new summary.
    vectors = await embed_texts(
        openai,
        [build_embedding_input(article.title, summary)],
        settings.embedding_model,
    )
    store_summary(db, article, summary, vectors[0])

    return {"summary": summary}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai_routes.py -v`
Expected: all 18 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/ai.py tests/test_ai_routes.py
git commit -m "feat: add on-demand article summary endpoint"
```

---

### Task 12: The `/chat/ask` endpoint

**Files:**
- Modify: `app/routes/ai.py`
- Test: `tests/test_ai_routes.py`

**Interfaces:**
- Produces: `POST /chat/ask` accepting `{"question": str}` → `{"answer": str, "sources": [article, ...]}`
- Consumes: `ensure_embeddings` (Task 10), `build_chat_messages` (Task 5), `find_similar` (Task 9), `complete`/`embed_texts` (Task 6).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai_routes.py`:

```python
def test_ask_answers_from_retrieved_articles(client, db_session):
    db_session.add_all([
        _article(1, "Rust is fast", embedding=[1.0] + [0.0] * 1535, summary="About Rust."),
        _article(2, "Go is simple", embedding=[0.0, 1.0] + [0.0] * 1534),
    ])
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.return_value = _chat_response("Rust is faster.")

    response = client.post("/chat/ask", json={"question": "Which is faster?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Rust is faster."
    # sources is the retrieved set that grounded the prompt, nearest first.
    assert [s["id"] for s in body["sources"]] == [1, 2]


def test_ask_embeds_the_question(client, db_session):
    db_session.add(_article(1, "a", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.return_value = _chat_response("An answer.")

    client.post("/chat/ask", json={"question": "Which is faster?"})

    assert client.mock.embeddings.create.await_args.kwargs["input"] == ["Which is faster?"]


def test_ask_backfills_embeddings_first(client, db_session):
    db_session.add_all([_article(1, "a"), _article(2, "b")])
    db_session.commit()
    client.mock.embeddings.create.side_effect = [
        _embedding_response([[1.0] + [0.0] * 1535, [0.5] * 1536]),  # backfill
        _embedding_response([[1.0] + [0.0] * 1535]),                # question
    ]
    client.mock.chat.completions.create.return_value = _chat_response("An answer.")

    response = client.post("/chat/ask", json={"question": "Anything?"})

    assert response.status_code == 200
    assert client.mock.embeddings.create.await_count == 2


def test_ask_includes_the_retrieved_articles_in_the_prompt(client, db_session):
    db_session.add(_article(1, "Rust is fast", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.return_value = _chat_response("An answer.")

    client.post("/chat/ask", json={"question": "Which is faster?"})

    prompt = client.mock.chat.completions.create.await_args.kwargs["messages"][1]["content"]
    assert "Rust is fast" in prompt
    assert "Which is faster?" in prompt


def test_ask_works_on_an_empty_corpus(client):
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.return_value = _chat_response("I have no articles.")

    response = client.post("/chat/ask", json={"question": "Anything?"})

    assert response.status_code == 200
    assert response.json()["sources"] == []


@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
def test_ask_rejects_blank_questions(client, question):
    # Review Focus 4: an empty string must never reach the embedding API.
    response = client.post("/chat/ask", json={"question": question})

    assert response.status_code == 422
    client.mock.embeddings.create.assert_not_awaited()


def test_ask_trims_the_question(client, db_session):
    db_session.add(_article(1, "a", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.return_value = _chat_response("An answer.")

    client.post("/chat/ask", json={"question": "  Which is faster?  "})

    assert client.mock.embeddings.create.await_args.kwargs["input"] == ["Which is faster?"]


def test_ask_requires_a_question_field(client):
    assert client.post("/chat/ask", json={}).status_code == 422


def test_ask_501s_without_an_api_key(unconfigured_client):
    response = unconfigured_client.post("/chat/ask", json={"question": "Anything?"})
    assert response.status_code == 501


def test_ask_503s_when_the_completion_fails(client, db_session):
    db_session.add(_article(1, "a", embedding=[1.0] + [0.0] * 1535))
    db_session.commit()
    client.mock.embeddings.create.return_value = _embedding_response([[1.0] + [0.0] * 1535])
    client.mock.chat.completions.create.side_effect = AiServiceError("boom")

    response = client.post("/chat/ask", json={"question": "Anything?"})

    assert response.status_code == 503
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai_routes.py -v`
Expected: the new tests FAIL with 404 (route not defined).

- [ ] **Step 3: Write the implementation**

Add to `app/routes/ai.py` — extend the imports with `from pydantic import BaseModel, field_validator` and `from app.domains.ai import build_chat_messages`, then:

```python
class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        # Returns the trimmed value, so a blank question is a 422 rather than an
        # empty string sent to the embedding API.
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("question must not be blank")
        return trimmed


@router.post("/chat/ask")
async def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    client: AsyncOpenAI | None = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    openai = require_client(client)
    await ensure_embeddings(db, openai, settings)

    question_vectors = await embed_texts(
        openai, [payload.question], settings.embedding_model
    )
    retrieved = find_similar(db, question_vectors[0], limit=RETRIEVAL_LIMIT)

    messages = build_chat_messages(payload.question, retrieved)
    answer = await complete(openai, messages, settings.openai_model)

    # sources is exactly the set that grounded the prompt -- the model cannot
    # cite anything it was not given.
    return {"answer": answer, "sources": [serialize_article(a) for a in retrieved]}
```

- [ ] **Step 4: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/ai.py tests/test_ai_routes.py
git commit -m "feat: add retrieval-grounded chat endpoint"
```

---

### Task 13: Frontend — three-state AI results

**Files:**
- Modify: `frontend/src/api/ai.ts`, `frontend/src/api/ai.test.ts`, `frontend/src/components/AiSummaryPanel.tsx`, `frontend/src/components/AiSummaryPanel.test.tsx`, `frontend/src/components/RelatedArticles.tsx`, `frontend/src/components/RelatedArticles.test.tsx`, `frontend/src/pages/AskAiPage.tsx`, `frontend/src/pages/AskAiPage.test.tsx`
- Delete: `frontend/src/components/ComingSoonBadge.tsx`, `frontend/src/components/ComingSoonBadge.test.tsx`

**Interfaces:**
- Produces: `AiResult<T> = { state: "ok"; data: T } | { state: "unconfigured" } | { state: "failed" }`
- Consumes: the backend status codes from Tasks 10-12 (`501` unconfigured, `503`/other failed).

- [ ] **Step 1: Write the failing tests for `ai.ts`**

Replace the body of `frontend/src/api/ai.test.ts` with:

```ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { getSummary, getRelated, askQuestion } from "./ai";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(status: number, body: unknown = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })
  );
}

describe("ai api", () => {
  it("returns ok with data on success", async () => {
    stubFetch(200, { summary: "A summary." });
    const result = await getSummary(1);
    expect(result).toEqual({ state: "ok", data: { summary: "A summary." } });
  });

  it("returns unconfigured on 501", async () => {
    stubFetch(501);
    expect(await getSummary(1)).toEqual({ state: "unconfigured" });
  });

  it("returns failed on 503", async () => {
    stubFetch(503);
    expect(await getSummary(1)).toEqual({ state: "failed" });
  });

  it("returns failed on 404", async () => {
    stubFetch(404);
    expect(await getSummary(1)).toEqual({ state: "failed" });
  });

  it("returns failed on a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    expect(await getRelated(1)).toEqual({ state: "failed" });
  });

  it("posts the question to /chat/ask", async () => {
    stubFetch(200, { answer: "An answer.", sources: [] });
    const result = await askQuestion("Which is faster?");
    expect(result).toEqual({ state: "ok", data: { answer: "An answer.", sources: [] } });
    expect(fetch).toHaveBeenCalledWith(
      "/api/chat/ask",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ question: "Which is faster?" }) })
    );
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npm test -- ai.test.ts`
Expected: FAIL — results come back as `{ available: ... }`, not `{ state: ... }`.

- [ ] **Step 3: Rewrite `ai.ts`**

```ts
import { apiFetch, ApiError } from "./client";
import type { Article } from "../types/article";

export type AiResult<T> =
  | { state: "ok"; data: T }
  | { state: "unconfigured" }   // 501 — no OPENAI_API_KEY configured
  | { state: "failed" };        // 503, any other non-2xx, or a network error

async function callAi<T>(path: string, init?: RequestInit): Promise<AiResult<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { state: "ok", data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 501) {
      return { state: "unconfigured" };
    }
    // Everything else is transient from the user's point of view: a 503, an
    // unexpected status, or a network failure all mean "try again".
    return { state: "failed" };
  }
}

export function getSummary(articleId: number): Promise<AiResult<{ summary: string }>> {
  return callAi(`/articles/${articleId}/summary`);
}

export function getRelated(articleId: number): Promise<AiResult<{ related: Article[] }>> {
  return callAi(`/articles/${articleId}/related`);
}

export function askQuestion(
  question: string
): Promise<AiResult<{ answer: string; sources: Article[] }>> {
  return callAi(`/chat/ask`, { method: "POST", body: JSON.stringify({ question }) });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- ai.test.ts`
Expected: all 6 PASS.

- [ ] **Step 5: Write the failing component tests**

Replace the body of `frontend/src/components/AiSummaryPanel.test.tsx` with:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../testUtils";
import { AiSummaryPanel } from "./AiSummaryPanel";
import * as ai from "../api/ai";

vi.mock("../api/ai");

beforeEach(() => vi.resetAllMocks());

describe("AiSummaryPanel", () => {
  it("renders the summary when available", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "ok", data: { summary: "A summary." } });
    renderWithProviders(<AiSummaryPanel articleId={1} />);
    await waitFor(() => expect(screen.getByText("A summary.")).toBeInTheDocument());
  });

  it("reports when AI is not configured", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "unconfigured" });
    renderWithProviders(<AiSummaryPanel articleId={1} />);
    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
  });

  it("offers a retry when generation failed", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "failed" });
    renderWithProviders(<AiSummaryPanel articleId={1} />);

    await waitFor(() => expect(screen.getByText(/couldn't generate/i)).toBeInTheDocument());

    vi.mocked(ai.getSummary).mockResolvedValue({ state: "ok", data: { summary: "Worked now." } });
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByText("Worked now.")).toBeInTheDocument());
  });

  it("never shows the retired Phase 2 placeholder", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "unconfigured" });
    renderWithProviders(<AiSummaryPanel articleId={1} />);
    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
    expect(screen.queryByText(/coming in Phase 2/)).not.toBeInTheDocument();
  });
});
```

Check `frontend/src/testUtils.tsx` for the existing helper name and signature and use it as-is; if it exports something other than `renderWithProviders`, adjust these imports to match rather than adding a second helper.

- [ ] **Step 6: Run them to verify they fail**

Run: `cd frontend && npm test -- AiSummaryPanel`
Expected: FAIL — the component renders `ComingSoonBadge`, so `/not configured/` is not found.

- [ ] **Step 7: Rewrite `AiSummaryPanel.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { getSummary } from "../api/ai";

export function AiSummaryPanel({
  articleId,
  variant = "full",
}: {
  articleId: number;
  variant?: "compact" | "full";
}) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["summary", articleId],
    queryFn: () => getSummary(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading summary...</p>;
  }
  if (data?.state === "unconfigured") {
    return <p className="text-sm text-gray-400">AI features are not configured.</p>;
  }
  if (data?.state !== "ok") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Couldn't generate a summary.</span>
        <button className="rounded border border-gray-300 px-2 py-0.5" onClick={() => refetch()}>
          Try again
        </button>
      </div>
    );
  }
  return (
    <p className={variant === "compact" ? "line-clamp-2 text-sm text-gray-600" : "text-base text-gray-700"}>
      {data.data.summary}
    </p>
  );
}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd frontend && npm test -- AiSummaryPanel`
Expected: all 4 PASS.

- [ ] **Step 9: Apply the same three-state treatment to `RelatedArticles.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getRelated } from "../api/ai";

export function RelatedArticles({ articleId }: { articleId: number }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["related", articleId],
    queryFn: () => getRelated(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading related articles...</p>;
  }
  if (data?.state === "unconfigured") {
    return <p className="text-sm text-gray-400">AI features are not configured.</p>;
  }
  if (data?.state !== "ok") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Couldn't load related articles.</span>
        <button className="rounded border border-gray-300 px-2 py-0.5" onClick={() => refetch()}>
          Try again
        </button>
      </div>
    );
  }
  if (data.data.related.length === 0) {
    return <p className="text-sm text-gray-400">No related articles found.</p>;
  }
  return (
    <ul className="space-y-2">
      {data.data.related.map((article) => (
        <li key={article.id}>
          <Link to={`/articles/${article.id}`} className="text-blue-600 hover:underline">
            {article.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}
```

Update `RelatedArticles.test.tsx` the same way as Step 5 — one test per state (`ok` renders the titles, `unconfigured` shows the note, `failed` offers a retry) plus a case asserting the empty-corpus message, replacing every `{ available: ... }` fixture with `{ state: ... }`.

- [ ] **Step 10: Update `AskAiPage.tsx`**

Replace the `ChatTurn` type and `handleSend`, and the turn rendering:

```tsx
interface ChatTurn {
  question: string;
  state: "ok" | "unconfigured" | "failed";
  answer: string | null;
}

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed || isAsking) return;
    setIsAsking(true);
    setQuestion("");
    const result = await askQuestion(trimmed);
    setTurns((prev) => [
      ...prev,
      {
        question: trimmed,
        state: result.state,
        answer: result.state === "ok" ? result.data.answer : null,
      },
    ]);
    setIsAsking(false);
  }
```

`callAi` never throws, so the previous `try`/`catch` is gone. Render per state:

```tsx
            {turn.state === "ok" && <p className="mt-1 text-gray-700">{turn.answer}</p>}
            {turn.state === "unconfigured" && (
              <p className="mt-1 text-sm text-gray-500">AI features are not configured.</p>
            )}
            {turn.state === "failed" && (
              <p className="mt-1 text-sm text-gray-500">
                Couldn't answer that right now. Please try again.
              </p>
            )}
```

Update `AskAiPage.test.tsx` to mock `askQuestion` returning each of the three states and assert the matching text, replacing the `/coming in Phase 2/` assertion.

- [ ] **Step 11: Delete the placeholder component**

```bash
cd frontend && rm src/components/ComingSoonBadge.tsx src/components/ComingSoonBadge.test.tsx
```

- [ ] **Step 12: Verify nothing still references it**

Run: `cd frontend && grep -rn "ComingSoonBadge\|coming in Phase 2" src/ || echo "clean"`
Expected: `clean`.

- [ ] **Step 13: Run the full frontend suite and the type check**

Run: `cd frontend && npm test -- --run && npx tsc --noEmit`
Expected: all tests PASS, no type errors. `tsc` is the guard that every `{ available: ... }` usage was migrated.

- [ ] **Step 14: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): replace coming-soon badge with real AI states"
```

---

### Task 14: Documentation and end-to-end verification

**Files:**
- Modify: `README.md`
- Test: manual verification against the real OpenAI API and the real database.

**Interfaces:**
- Consumes: the complete running stack from Tasks 1-13.
- Produces: nothing new — a verification pass plus docs.

- [ ] **Step 1: Document Phase 2 in the README**

Replace the opening paragraph's "No AI features in the backend yet (see Phase 2)" sentence, and add a section:

```markdown
## AI features (Phase 2)

Set `OPENAI_API_KEY` in `.env` to enable them. Without a key the API returns
`501` on the AI endpoints and the UI shows "AI features are not configured" —
everything else works normally.

- `GET /articles/{id}/summary` — summarizes the linked page, falling back to the
  HN discussion for Ask HN posts and unfetchable links. Generated once per
  article on first request, then cached in the database forever.
- `GET /articles/{id}/related` — five nearest articles by embedding similarity.
- `POST /chat/ask` — `{"question": "..."}` returns an answer grounded in the
  five most relevant stored articles, plus those articles as `sources`.

Embeddings are backfilled corpus-wide on the first call to `/related` or
`/chat/ask` (one batched request, a couple of seconds), then incrementally as
refreshes add articles. Nothing is generated during `POST /articles/refresh`.

Models: `gpt-4o-mini` for generation, `text-embedding-3-small` for embeddings.
Override with `OPENAI_MODEL` and `EMBEDDING_MODEL`.

### Migrations

Schema is managed by Alembic and `alembic upgrade head` runs automatically on
startup. If you are upgrading a database created before Phase 2, run
`uv run alembic stamp head` once before starting the app so the Phase 1
baseline is not re-applied.
```

- [ ] **Step 2: Start the full stack**

Run: `docker compose up --build`
Expected: all four containers start; backend logs show the migration running and no errors.

- [ ] **Step 3: Verify the unconfigured path first**

With `OPENAI_API_KEY` empty, open an article at http://localhost:3000.
Expected: the article renders normally; the AI Summary and Related sections both read "AI features are not configured." No error banner, and **no** "coming in Phase 2" text anywhere.

- [ ] **Step 4: Configure the key and generate a summary**

Set `OPENAI_API_KEY` in `.env`, `docker compose up -d --force-recreate backend`, then open an article.
Expected: "Loading summary..." then a three-to-four-sentence summary. Confirm it persisted:

```bash
docker compose exec db psql -U hn_user -d hn_capstone \
  -c "select id, left(summary, 60), summary_generated_at from articles where summary is not null;"
```

- [ ] **Step 5: Confirm the cache**

Reload the same article page.
Expected: the summary appears immediately with no loading state. Backend logs show no new OpenAI call — this is Review Focus 5 verified against the real system.

- [ ] **Step 6: Verify the backfill and related articles**

Expected: the Related Articles section lists up to five plausibly-related titles. Confirm the corpus was embedded:

```bash
docker compose exec db psql -U hn_user -d hn_capstone \
  -c "select count(*) as total, count(embedding) as embedded from articles;"
```

Expected: `embedded` equals `total`.

- [ ] **Step 7: Verify the Ask HN fallback**

Find an article with no URL and open it:

```bash
docker compose exec db psql -U hn_user -d hn_capstone \
  -c "select id, title from articles where url is null limit 5;"
```

Expected: a summary is still produced, describing the discussion. This is Review Focus 1 against real HN data.

- [ ] **Step 8: Verify chat**

Go to http://localhost:3000/ask and ask something answerable from the corpus, e.g. "What are people saying about AI models?"
Expected: a grounded answer. Then ask something absent from the corpus, e.g. "What is the capital of France?"
Expected: the model says the articles do not cover it rather than answering from general knowledge.

- [ ] **Step 9: Verify the failure path**

Set `OPENAI_API_KEY` to an invalid value, recreate the backend, and open an un-summarized article.
Expected: "Couldn't generate a summary." with a working "Try again" button — not a blank panel and not "not configured".

- [ ] **Step 10: Run both suites one final time**

Run: `uv run pytest -q` and `cd frontend && npm test -- --run && npx tsc --noEmit`
Expected: everything passes.

- [ ] **Step 11: Record the verification and commit**

Append to the "Verified" section of `README.md`:

```markdown
Phase 2 AI features manually smoke-tested end-to-end against the real OpenAI
API on 2026-10-07: unconfigured degradation, summary generation and caching,
the Ask HN comment fallback, corpus embedding backfill, related articles,
grounded chat with and without relevant articles, and the invalid-key failure
path all behave as designed.
```

```bash
git add README.md
git commit -m "docs: document Phase 2 AI features and record smoke test"
```
