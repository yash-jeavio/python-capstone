# Hacker News AI Insights — Phase 2 AI Features Design Spec

**Date**: 2026-10-07
**Scope**: AIB-512 — AI summarization, recommendations, and grounded Q&A built on the Phase 1 backend (AIB-511) and the Phase 2 frontend contract already shipped by the React UI phase.

## Purpose

Phase 2 is the AI-engineering half of the capstone. It adds three capabilities on top of the existing aggregator: an on-demand summary per article, embedding-based related-article recommendations, and a retrieval-grounded Q&A endpoint over the stored corpus.

The frontend for all three already exists. `src/api/ai.ts` and the `AiSummaryPanel`, `RelatedArticles`, and `AskAiPage` components were built during the React UI phase against a fixed contract and currently render a "coming in Phase 2" placeholder. This spec implements the backend half of that contract and replaces the placeholder with real unavailable/error states.

Because this is a learning project, the design favors patterns worth learning (a real vector store, real migrations, layered testing) over the minimum that would function at this corpus size.

## Tech stack decisions

- **Provider**: OpenAI. `gpt-4o-mini` for summarization and chat answers, `text-embedding-3-small` (1536 dims) for embeddings. `gpt-4o-mini` is adequate for summarizing a fetched page and answering over retrieved context, at a cost that permits free experimentation.
- **Vector store**: `pgvector` in the existing Postgres, not in-process numpy. At ~295 articles numpy would be instant, but loading the whole corpus per request is a pattern that stops working as the corpus grows; pgvector keeps retrieval in SQL where it belongs.
- **Migrations**: Alembic, introduced in this phase. Phase 1 created schema with `Base.metadata.create_all()`, which creates missing tables but will not add columns to the existing `articles` table.
- **Content extraction**: a readable-text extraction library (e.g. `trafilatura`) over raw HTML parsing, so paywall and boilerplate handling is not hand-rolled.

## Generation strategy

Generation is **lazy** — nothing is generated during `POST /articles/refresh`. The two operations are treated asymmetrically because their costs differ by orders of magnitude:

- **Summaries** are strictly per-article and on demand. A summary requires fetching the linked page and a `gpt-4o-mini` call, so it happens only for articles a user actually opens. It is stored and reused permanently.
- **Embeddings** are corpus-wide, backfilled on first need. `/related` and `/chat/ask` are corpus operations: comparing one article against an otherwise-unembedded corpus returns nothing useful, and retrieval over a near-empty index cannot ground an answer. Embedding every article costs a fraction of a cent and roughly two seconds in one batched call, so the first request to either endpoint embeds all articles missing a vector, then serves the request. Subsequent calls embed only what a refresh has added since.

This honors "no work at refresh time" while leaving both corpus features functional from the first use.

### Embedding input

An article's vector is built from **title + summary when a summary exists**, title alone otherwise. This keeps the corpus fully covered at all times (titles are always available, no fetching required) while improving vector quality on articles people actually engage with.

No "does this vector include the summary?" column is needed. The invariant is maintained by two rules:

1. Backfill targets only rows `WHERE embedding IS NULL`.
2. Writing a summary immediately re-embeds that one article in the same request.

The full scraped page text is deliberately **not** embedded. Doing so would require fetching every linked page before the corpus became usable — minutes of wall-clock and a large scrape-failure surface — in exchange for quality the corpus features do not need.

## Architecture & data flow

```
Browser :3000 ── nginx ──/api/*──► FastAPI :8000
                                      │
                      ┌───────────────┼────────────────┐
                      │               │                │
              routes/articles.py  routes/ai.py    (existing)
                                      │
                      ┌───────────────┼────────────────┐
                      ▼               ▼                ▼
              domains/ai.py   network/openai_   network/content_
              (pure: prompts,  client.py        fetcher.py
               embed input,   (embed/summarize/ (fetch URL →
               truncation)     answer)           readable text)
                      │               │                │
                      └───────────────┼────────────────┘
                                      ▼
                          database/repository.py
                                      │
                                      ▼
                     Postgres + pgvector (articles table)
```

The Phase 1 four-layer split is preserved: the domain layer stays pure and framework-agnostic, network modules own all outbound I/O and know nothing about the database, the repository owns all SQL, and routes compose them.

## Project structure

New files:

| File | Layer | Responsibility |
|---|---|---|
| `app/network/openai_client.py` | Network | `embed_texts()`, `summarize()`, `answer_question()`. Accepts an injected client so tests can mock it. No DB access. |
| `app/network/content_fetcher.py` | Network | Fetch `article.url`, extract readable text, signal failure so the caller can fall back. |
| `app/domains/ai.py` | Domain | Pure functions: embedding-input assembly, summarization prompt, RAG prompt, token-budget truncation. No I/O. |
| `app/routes/ai.py` | Routes | The three endpoints. Registered as a second router in `main.py`. |
| `alembic/`, `alembic.ini` | Infra | Migration tree. |

Modified files:

| File | Change |
|---|---|
| `app/database/models.py` | Three new columns (below). |
| `app/database/repository.py` | `articles_missing_embeddings()`, `store_embedding()`, `store_summary()`, `find_similar()`. |
| `app/network/hn_client.py` | `fetch_comments(item_id)` for the summarization fallback — it already owns HN API access. |
| `app/common/config.py` | Three new settings (below). |
| `app/main.py` | Register the `ai` router; replace the `create_all` call in `lifespan` with `alembic upgrade head` (see "Schema ownership" below). |
| `app/routes/articles.py` | Extract a shared `serialize_article()` helper (see below). |
| `tests/conftest.py` | `CREATE EXTENSION IF NOT EXISTS vector` before `create_all`. |
| `docker-compose.yml` | pgvector image for both Postgres services; pass `OPENAI_API_KEY` to backend. |
| `.env.example`, `README.md` | Document the new key and setup. |

### Incidental cleanup

The article-to-dict serialization is already duplicated in `app/routes/articles.py` (in `list_articles` and `get_article`). Phase 2 would add two more copies, for `/related` and for `/chat/ask`'s `sources`. This phase extracts a single `serialize_article()` helper and routes all four call sites through it. This is in scope because Phase 2 is the change that makes the duplication costly; no other refactoring is included.

## Data model

Three new nullable columns on `articles`. Per the Phase 1 spec's "new columns, not new tables" guidance, no new table is introduced.

| Column | Type | Notes |
|---|---|---|
| `summary` | `TEXT NULL` | Generated once, reused permanently. `NULL` means "not yet generated". |
| `summary_generated_at` | `TIMESTAMPTZ NULL` | Provenance; also distinguishes "never generated" from a future empty-summary case. |
| `embedding` | `VECTOR(1536) NULL` | `NULL` is the backfill target. Dimension is fixed by `text-embedding-3-small`. |

`CREATE EXTENSION IF NOT EXISTS vector` must run before the `embedding` column can be created. The extension is per-database, not per-image, so it is required in **two** places: the first Alembic migration (for the dev database) and the `db_session` fixture (for the test database).

### Schema ownership after Alembic

Introducing Alembic creates an ambiguity with Phase 1's `Base.metadata.create_all(engine)`, currently called in the `lifespan` hook at `app/main.py:18`. The split is:

- **Dev and production schema is owned by Alembic.** The `create_all` call is **removed** from `lifespan`, which instead runs `alembic upgrade head` programmatically on startup so a `docker compose up` still produces a working database with no manual step. Two sources of schema truth would otherwise drift the moment a migration does anything `create_all` cannot express.
- **Test schema stays on `create_all`.** `tests/conftest.py` keeps its `create_all` / `drop_all` cycle per test, preceded by the extension statement. Running the full migration history for every test would be slow and would couple unit tests to migration correctness. The tradeoff is accepted: a divergence between models and migrations would not be caught by the test suite, so the first migration is generated with `alembic revision --autogenerate` from the models rather than hand-written.

## API endpoints

All three paths are fixed by the existing frontend contract in `src/api/ai.ts` and must not drift.

### `GET /articles/{id}/summary`

Returns `{ "summary": str }`.

1. Load the article; `404` if absent.
2. If `article.summary` is set, return it. **No API call.** This check precedes the API-key check, so already-summarized articles keep working without a key.
3. If `openai_api_key` is unset, `501`.
4. Acquire content: fetch and extract `article.url` when present; on absence or failure, fall back to the article's **top 10 top-level HN comments** (via `fetch_comments`, concatenated in HN's own ranking order). If both fail, `503`.
5. Truncate the content to **12,000 characters** (roughly 3,000 tokens), cutting at a whitespace boundary. This constant lives in `domains/ai.py` and is the single definition of the token budget referenced elsewhere in this spec; it bounds worst-case cost per summary and sits far inside the model's context window.
6. Summarize via `gpt-4o-mini`.
7. Store `summary` and `summary_generated_at`; re-embed this article from title + summary.
8. Return the summary.

### `GET /articles/{id}/related`

Returns `{ "related": [Article, ...] }`, at most 5.

1. Load the article; `404` if absent.
2. If `openai_api_key` is unset, `501`.
3. Run the shared embedding backfill.
4. `ORDER BY embedding <=> :this_embedding LIMIT 5`, excluding the article itself.
5. Return the articles, serialized in the standard shape.

### `POST /chat/ask`

Accepts `{ "question": str }`, returns `{ "answer": str, "sources": [Article, ...] }`.

1. If `openai_api_key` is unset, `501`.
2. Run the shared embedding backfill.
3. Embed the question.
4. Retrieve the top 5 articles by cosine distance.
5. Build a grounded prompt from those articles' title, summary, url, and score.
6. Answer via `gpt-4o-mini`.
7. Return the answer with those same 5 articles as `sources`.

**Stateless by design.** `AskAiPage` keeps conversation turns in client state and sends only `{question}`, so no history is stored and no session table exists. `sources` is the retrieved set that grounded the prompt, not a post-hoc citation — the model cannot cite what it was not given.

### Shared embedding backfill

Both corpus endpoints call one idempotent `ensure_embeddings(db)`: select rows `WHERE embedding IS NULL`, embed their titles (plus summaries where present) in a single batched request, store the vectors. On a fresh database the first call embeds the whole corpus; afterwards it embeds only articles added by the most recent refresh, and is a no-op when nothing is missing.

## Error handling

### Backend

| Condition | Status |
|---|---|
| Article not found | `404` |
| `openai_api_key` unset | `501` |
| OpenAI error, timeout, or rate limit | `503` |
| Page fetch *and* comment fallback both failed | `503` |
| Unforeseen | `500` via the existing handler in `app/main.py` |

`501` means "not configured" — permanent and expected, not a fault. `503` means "try again" — transient.

### Frontend

The current components cannot express this. `AiSummaryPanel` and `RelatedArticles` test only `!data?.available`, and TanStack Query leaves `data` undefined when the query function throws — so **any** backend failure currently renders "coming in Phase 2", a message that becomes false the moment this phase ships.

`AiResult<T>` therefore goes from two states to three:

```ts
export type AiResult<T> =
  | { state: "ok"; data: T }
  | { state: "unconfigured" }   // 501
  | { state: "failed" };        // 503 / network
```

The response-to-state mapping in `ai.ts` is exhaustive:

| Response | State |
|---|---|
| `2xx` | `ok` |
| `501` | `unconfigured` |
| `503`, any other non-2xx, or a network `TypeError` | `failed` |
| `404` | `failed` — the article itself is gone, and `ArticleDetailPage` already renders its own "article not found" state as the primary signal, so these panels only need to stop rendering stale content |

| State | UI |
|---|---|
| `ok` | The summary / related list / answer |
| `unconfigured` | A quiet "AI features not configured" note |
| `failed` | "Couldn't generate — try again" plus a retry button wired to TanStack Query's `refetch` |

`ComingSoonBadge.tsx` and `ComingSoonBadge.test.tsx` are **deleted**; the component existed only to stand in for this phase. Its four consumer tests are updated to assert the new states.

## Cost control

Caching is the only guard, deliberately. A summary is generated once per article and stored permanently, so the ceiling is one summarization per article in a ~295-row corpus — a few cents in total. `/chat/ask` is uncached but is a single inexpensive call per question. Rate limiting and spend ceilings are rejected as YAGNI for a single-user learning project.

## Testing approach

Mirrors Phase 1: each layer is tested where it is cheapest, and **no test ever calls OpenAI or scrapes a live page.**

| Target | Method |
|---|---|
| `domains/ai.py` | No mocks. Prompt construction, embedding-input assembly, truncation at the token budget. |
| `network/openai_client.py` | `AsyncMock(spec=...)` injected client, following `tests/test_hn_client.py`. Success, rate-limit, timeout. |
| `network/content_fetcher.py` | Mocked responses: clean HTML, boilerplate/paywall, non-HTML, timeout. Asserts extraction and the failure signal that triggers the fallback. |
| `database/repository.py` | Real test Postgres via `db_session`; pgvector's `<=>` cannot be meaningfully mocked. Known vectors, asserting ordering and self-exclusion. |
| `routes/ai.py` | `TestClient` with the OpenAI client patched. Cache hit asserting **zero** API calls, `404`, `501` with no key, `503` on failure, and that writing a summary triggers a re-embed. |
| Frontend | The four existing AI component tests updated from two states to three. |

## Out of scope for this spec

- **Automatic or scheduled refresh.** Refresh stays manual by explicit decision; it is unrelated to AI.
- **Conversation history / multi-turn context** in `/chat/ask`.
- **Rate limiting or spend ceilings.** Caching is the guard.
- **Streaming responses.**
- **Re-summarizing** when an article's score or comment count changes. A summary is written once.
- **Embedding full page text.** Vectors are title + summary only.
- **Re-ranking, hybrid keyword+vector search, or chunking.** Single-vector-per-article retrieval is sufficient at this corpus size.
