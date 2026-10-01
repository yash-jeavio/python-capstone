# Hacker News Aggregator

Fetches stories from the public Hacker News API, stores them in PostgreSQL,
and exposes them through a filterable REST API (Phase 1 backend), plus a
React frontend for browsing them. No AI features in the backend yet (see
Phase 2) — the "Ask AI" UI exists but shows a coming-soon state until then.

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

## Verified

Manually smoke-tested end-to-end against the real Hacker News API on 2026-09-30:
refresh, filtered listing, single-article lookup (including 404), and
idempotent re-refresh all behave as designed.
