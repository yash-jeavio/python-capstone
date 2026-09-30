# Hacker News Backend Aggregator (Phase 1)

Fetches stories from the public Hacker News API, stores them in PostgreSQL,
and exposes them through a filterable REST API. No AI features (see Phase 2).

## Setup

1. Copy `.env.example` to `.env`.
2. `docker compose up -d` — starts dev Postgres (5432) and test Postgres (5433).
3. `uv sync` — installs dependencies.
4. `uv run uvicorn app.main:app --reload` — starts the API at http://127.0.0.1:8000.
5. `uv run pytest` — runs the test suite (uses the test Postgres container).

## Verified

Manually smoke-tested end-to-end against the real Hacker News API on 2026-09-30:
refresh, filtered listing, single-article lookup (including 404), and
idempotent re-refresh all behave as designed.
