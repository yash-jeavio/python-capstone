# Hacker News Aggregator

Fetches stories from the public Hacker News API, stores them in PostgreSQL,
and exposes them through a filterable REST API (Phase 1 backend), plus a
React frontend for browsing them. Phase 2 adds AI-powered summaries, related
articles, and a grounded chat assistant — see "AI features (Phase 2)" below.

## Backend setup (Phase 1)

1. Copy `.env.example` to `.env`.
2. `docker compose up -d` — starts dev Postgres (5435), test Postgres (5434),
   and now also a `backend` container (127.0.0.1:8000) and a `frontend`
   container (127.0.0.1:3000). If you only want the DB for local development
   against step 4 below, either stop the containerized backend
   (`docker compose stop backend`) or bring up just the databases
   (`docker compose up -d db test-db`) to avoid a port conflict on 8000.
3. `uv sync` — installs dependencies.
4. `uv run uvicorn app.main:app --reload` — starts the API at http://127.0.0.1:8000.
5. `uv run pytest` — runs the test suite (uses the test Postgres container).

## Full stack (UI + Backend + DB)

`docker compose up --build` — builds and starts the database, backend API,
and React frontend together. Open http://localhost:3000 for the UI.

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

## Verified

Manually smoke-tested end-to-end against the real Hacker News API on 2026-09-30:
refresh, filtered listing, single-article lookup (including 404), and
idempotent re-refresh all behave as designed.

Phase 2 AI features verified on 2026-10-08 to the extent possible without an
OpenAI API key: the full stack builds and starts, migrations apply cleanly, the
articles list and detail pages work unchanged, and with no key configured the AI
endpoints return 501 and the UI shows "AI features are not configured" rather
than an error. Generation, caching, embedding backfill, related articles, and
grounded chat require a key and remain unverified against the live API.
