# Hacker News AI Insights — Phase 1 Design Spec

**Date**: 2026-09-30
**Scope**: AIB-511 — Backend-only news aggregator (no AI). Phase 2 (AIB-512) builds AI features on top of this and is out of scope for this spec.

## Purpose

Final capstone project of a structured Python learning path (fundamentals -> AI engineering). Phase 1 combines SQLAlchemy ORM, REST API design, async I/O, and testing into one real backend service: a Hacker News aggregator that fetches, stores, and exposes real HN stories through a filterable REST API — solid enough that Phase 2 can add AI summarization/recommendations on top without restructuring.

## Tech stack decisions

- **Framework**: FastAPI, chosen over Flask for native async support (this service makes many concurrent outbound HTTP calls) and automatic request validation/docs from Python type hints.
- **Database**: PostgreSQL, run in a dedicated Docker container (`docker-compose.yml`), chosen deliberately over SQLite for backend-realism practice and to use Postgres-native features (array columns).
- **Dependency management**: `pyproject.toml` + `uv`.
- **Project structure**: layered, framework-agnostic domain layer at the center. See "Architecture" below.

## Architecture & data flow

```
Client (curl / browser)
   |
   v
app/routes/articles.py          (FastAPI endpoints — HTTP boundary)
   |
   |--> POST /articles/refresh
   |       |
   |       v
   |    app/network/hn_client.py   -> calls the real Hacker News public API
   |       |                            (topstories, beststories, askstories, showstories)
   |       v
   |    app/domains/article.py    -> dedupes by HN id, merges source tags,
   |       |                            applies business rules (framework/DB-agnostic)
   |       v
   |    app/database/models.py + session.py   -> upsert into Postgres
   |
   |--> GET /articles?keyword=&min_score=&source=&sort=&page=
   |       |
   |       v
   |    database (query, filter, paginate)
   |       |
   |       v
   |    JSON response
   |
   |--> GET /articles/{id}
           |
           v
        database (lookup by HN id) -> JSON response, or 404
```

**Core design principle**: `app/domains/article.py` never imports SQLAlchemy, FastAPI, or an HTTP client. It receives plain data in, returns plain data out. Only `app/routes/` and `app/database/` touch FastAPI/Postgres directly, and only `app/network/` touches HTTP. This keeps the actual business logic (dedup rules, merge rules) unit-testable with zero mocking, and keeps the project able to swap any one layer (e.g. Postgres for something else) without touching the others.

**Refresh is async**: `POST /articles/refresh` fetches from all 4 HN lists and fetches each item's details concurrently (same pattern as the `AsyncFetcher` class from AIB-502), since this endpoint is dominated by waiting on many independent network calls, not computation.

## Project structure

```
hacker-news-capstone/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app instance, wires everything together
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings, reads .env
│   │   └── logging.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py                # SQLAlchemy engine + session setup
│   │   └── models.py                  # ORM table definitions
│   ├── domains/
│   │   ├── __init__.py
│   │   └── article.py                 # business logic, no DB/framework imports
│   ├── network/
│   │   ├── __init__.py
│   │   └── hn_client.py                # the Hacker News API client
│   └── routes/
│       ├── __init__.py
│       └── articles.py                 # the actual endpoints
├── tests/
│   ├── test_hn_client.py
│   ├── test_article_domain.py
│   └── test_articles_routes.py
├── docker-compose.yml              # defines two services: dev Postgres (persistent volume)
│                                     # and test Postgres (no volume — disposable, wiped each run)
├── .env                            # real secrets — never committed
├── .env.example                     # template with placeholder values, committed
├── .gitignore
├── pyproject.toml                   # dependencies + project metadata
└── README.md
```

## Data model

One table: `articles`.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER`, primary key | HN's own item id — a natural key, not auto-generated. Makes upsert trivial and avoids positional-index fragility. |
| `title` | `TEXT`, not null | |
| `url` | `TEXT`, nullable | Ask HN posts often have no URL |
| `author` | `TEXT`, nullable | HN's `by` field |
| `score` | `INTEGER`, default 0 | Updated on every refresh |
| `comment_count` | `INTEGER`, default 0 | HN's `descendants` field |
| `item_type` | `TEXT`, not null | HN's own `type` field (`story`, `job`, etc.) |
| `sources` | `ARRAY(TEXT)`, not null | Which HN list(s) this article came from, e.g. `['top', 'best']`. Native Postgres array column. |
| `posted_at` | `TIMESTAMP`, not null | Converted from HN's raw Unix `time` field |
| `fetched_at` | `TIMESTAMP`, not null | When our system last refreshed this row |

**Upsert behavior**: `INSERT ... ON CONFLICT (id) DO UPDATE` — an article appearing in multiple HN lists (e.g. both `top` and `best`) becomes one row with a merged `sources` array, not duplicate rows.

**Deliberately one table, not more**: `sources` as an array column avoids needing a separate lookup + join table for a small, fixed set of 4 possible values (YAGNI). Phase 2's likely additions (an embedding vector, a summary) are expected to be new *columns* on this same table (1:1 with an article), not new tables.

## API endpoints

### `POST /articles/refresh`
Fetches top/best/ask/show lists (~30 items each) from HN concurrently, upserts into `articles`. Returns a summary, not the full list:
```json
{ "fetched": 118, "created": 94, "updated": 24, "failed": 2 }
```
Individual HN item-lookup failures (timeout/5xx/connection error) are best-effort: skipped and counted in `failed`, not fatal to the whole refresh.

### `GET /articles`
Filterable list endpoint. Query params:
- `keyword` — case-insensitive partial match on title
- `min_score` — minimum score threshold
- `source` — filter to one of `top`/`best`/`ask`/`show`
- `sort` — e.g. `score_desc`, `posted_at_desc`
- `page`, `page_size` — pagination

### `GET /articles/{id}`
Single article by HN id. `404` if not present locally.

**Deliberately no `POST`/`PUT`/`DELETE` on individual articles** — all article data flows in from HN via `/refresh`; clients never create/edit articles directly. This is a bulk-upsert-in, read-only-out service.

## Error handling

| Situation | Response |
|---|---|
| HN item fetch fails during refresh | Best-effort: skip, count in `failed`, continue |
| `GET /articles/{id}` not found | `404`, clean JSON body |
| Bad query params (e.g. non-numeric `min_score`) | `422`, automatic via FastAPI/Pydantic |
| DB connection lost / unexpected exception | Global exception handler returns a clean `500`, logs the real error server-side, never leaks a raw traceback to the client |

## Testing approach

- **`app/domains/article.py`**: plain `pytest` functions, no mocking — pure functions in, pure data out.
- **`app/network/hn_client.py`**: mock the actual HTTP calls (`unittest.mock`, same pattern as `test_fetchers.py` in the fundamentals track) — tests never hit the real Hacker News API.
- **`app/routes/`**: FastAPI's built-in `TestClient`, run against a **real, disposable Postgres container** (via Docker, separate from the dev database) for full fidelity — deliberately not SQLite, since SQLite doesn't support the native `ARRAY` column type this schema relies on.

## Out of scope for this spec

- Any AI features (summarization, embeddings, recommendations, RAG) — Phase 2 / AIB-512, separate spec.
- Scheduled/background refresh — on-demand only for Phase 1; scheduling is a possible later enhancement.
- User accounts / auth — not needed, this is a personal capstone project with no multi-user concerns.
- `new` HN story list — intentionally excluded (mostly unvetted/noisy); `top`/`best`/`ask`/`show` cover the intended variety.
