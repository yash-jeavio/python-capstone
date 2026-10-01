# Hacker News AI Insights — React UI & Docker Unification Design Spec

**Date**: 2026-10-01
**Scope**: New React frontend covering the existing Phase 1 (AIB-511) API, with UI built out for the planned AIB-512 AI features (summary, semantic search/related articles, RAG-style Q&A) as stub-aware components. Plus: Dockerizing the backend and frontend and unifying everything into one `docker-compose.yml` so the full stack (UI + backend + DB) starts with a single command.

**Out of scope**: Implementing the AIB-512 AI backend endpoints themselves. This spec only builds the frontend UI and API client contracts for them; the endpoints are expected to 404/501 until Phase 2 backend work lands.

## Purpose

Phase 1 (AIB-511) delivered a backend-only Hacker News aggregator, tested via Swagger. The next step is a usable web UI covering all current (and soon-to-come) features from the AI Bootcamp capstone, plus a one-command local environment (`docker compose up --build`) that runs the database, backend API, and frontend together — matching how the project will actually be demoed/used, not just hit via `curl`/Swagger.

## Tech stack decisions

- **Build tool**: Vite — fast dev server, standard modern choice over Create React App (deprecated).
- **Language**: TypeScript — catches API-shape drift against the backend at compile time rather than at runtime.
- **Styling**: Tailwind CSS — utility-first, avoids hand-rolled stylesheets for a project this size.
- **Routing**: React Router — 3 top-level pages (list, detail, ask-AI).
- **Data fetching**: TanStack Query — handles loading/error/caching/retry for filtered, paginated, mutable (refresh) data without hand-rolled `useEffect` fetch logic.
- **Container runtime**: Nginx (production build) serving the Vite static output — chosen over running the Vite dev server in Docker, since the goal is "one command, it just works," not live-editing inside the container.

## Architecture & data flow

```
Browser
   |
   v
Nginx (frontend container, :3000 -> :80)
   |--> static assets (React SPA, client-side routing)
   |--> /api/*  --(proxy_pass)-->  FastAPI backend container (:8000)
                                        |
                                        v
                                   Postgres (db container, :5432)
```

In local (non-Docker) dev, Vite's dev server proxies `/api` to `http://localhost:8000` directly — the frontend code always calls relative `/api/...` paths, so it behaves identically in both modes with no env-var branching.

**Core design principle (mirrors the backend's layering)**: `src/api/*` is the only code that knows about `fetch`/HTTP. Pages and components call typed functions (`listArticles(filters)`, `getArticle(id)`) and receive plain data or a typed `{available: false}` result — never a raw `Response` or fetch error.

## Project structure

```
Hacker-News-Capstone/
├── app/                           # existing FastAPI backend (unchanged)
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts           # base fetch wrapper (baseURL, JSON parsing, error typing)
│   │   │   ├── articles.ts         # listArticles, getArticle, refreshArticles
│   │   │   └── ai.ts               # getSummary, getRelated, askQuestion (stub-aware)
│   │   ├── components/
│   │   │   ├── ArticleCard.tsx
│   │   │   ├── ArticleFilters.tsx
│   │   │   ├── Pagination.tsx
│   │   │   ├── RefreshButton.tsx
│   │   │   ├── AiSummaryPanel.tsx
│   │   │   ├── RelatedArticles.tsx
│   │   │   └── ComingSoonBadge.tsx
│   │   ├── pages/
│   │   │   ├── ArticlesListPage.tsx
│   │   │   ├── ArticleDetailPage.tsx
│   │   │   └── AskAiPage.tsx
│   │   ├── types/article.ts        # mirrors backend's article JSON shape
│   │   ├── App.tsx                 # router + layout/nav + error boundary
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts              # dev-server proxy: /api -> localhost:8000
│   ├── tailwind.config.js
│   ├── package.json
│   ├── tsconfig.json
│   ├── nginx.conf                  # SPA fallback + /api proxy_pass to backend:8000
│   └── Dockerfile                  # multi-stage: node build -> nginx
├── Dockerfile                       # new: backend container (uv + uvicorn)
├── docker-compose.yml                # extended: + backend, + frontend services
└── docs/...
```

## Pages & components

### `ArticlesListPage` (`/`)
- Filter bar: debounced `keyword` text input, `min_score` number input, `source` dropdown (`top`/`best`/`ask`/`show`/all), `sort` dropdown (`score_desc`/`posted_at_desc`).
- `RefreshButton`: calls `POST /articles/refresh`, shows a loading state, then a toast with `{fetched, created, updated, failed}`; invalidates the articles query on success.
- Paginated grid of `ArticleCard` (title, author, score, comment_count, source badges, posted_at, outbound link to the HN `url`, link to the detail page). Each card shows a collapsed `AiSummaryPanel` teaser.
- `Pagination`: **current `GET /articles` returns a bare array with no total count**, so pagination is Prev/Next-based — disable "Next" when a page returns fewer than `page_size` items, rather than numbered pages against a known total.

### `ArticleDetailPage` (`/articles/:id`)
- Full article fields from `GET /articles/{id}`; a 404 renders an "Article not found" state with a link back to the list.
- `AiSummaryPanel` (expanded) — calls `GET /articles/{id}/summary` (stub endpoint, not yet on the backend).
- `RelatedArticles` — calls `GET /articles/{id}/related` (stub endpoint, semantic recommendations).

### `AskAiPage` (`/ask`)
- Chat-style UI: text input + send button, scrolling list of Q/A turns held in local component state (not persisted).
- Calls `POST /chat/ask` with `{ question }` (stub endpoint, RAG-style Q&A over stored articles).

## API contract

**Existing endpoints, used as-is (no backend changes)**:
- `GET /articles?keyword=&min_score=&source=&sort=&page=&page_size=`
- `GET /articles/{id}`
- `POST /articles/refresh`

**New stub endpoints the frontend calls, which Phase 2 (AIB-512) must implement**:
- `GET /articles/{id}/summary` → `{ summary: string }`
- `GET /articles/{id}/related` → `{ related: Article[] }`
- `POST /chat/ask` with `{ question: string }` → `{ answer: string, sources: Article[] }`

**Stub-endpoint handling**: `src/api/ai.ts` wraps each of these three calls so that a `404`/`501`/network error resolves to `{ available: false }` instead of throwing. The corresponding component (`AiSummaryPanel`, `RelatedArticles`, `AskAiPage`) renders `ComingSoonBadge` ("AI feature coming in Phase 2") in that case. This is the one deliberate departure from "let errors surface" — these three endpoints are known-not-yet-built, not a real failure, and no other API call gets this treatment.

## Error handling

| Situation | UI behavior |
|---|---|
| `GET /articles` network/5xx error | Error banner with a "Retry" button (TanStack Query refetch) |
| `GET /articles/{id}` 404 | "Article not found" empty state, link back to list |
| `POST /articles/refresh` fails | Toast with error message; existing list stays untouched |
| AI endpoints (`summary`/`related`/`chat/ask`) 404/501/network error | `ComingSoonBadge`, not an error banner |
| Invalid filter input (e.g. negative `min_score`) | Constrained client-side via input attributes, backing up the backend's existing `422` validation |
| Unexpected JS error anywhere in the tree | Top-level React error boundary around `<App />` shows a generic fallback instead of a blank screen |

## Docker

**`Dockerfile`** (repo root — backend):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`frontend/Dockerfile`** (multi-stage):
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

`frontend/nginx.conf`: serves the SPA with fallback to `index.html` for client-side routing; `location /api/ { proxy_pass http://backend:8000/; }`.

**`docker-compose.yml`** — existing `db`/`test-db` untouched, add:
```yaml
  backend:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg2://hn_user:hn_password@db:5432/hn_capstone
    depends_on:
      - db
    ports:
      - "127.0.0.1:8000:8000"

  frontend:
    build: ./frontend
    depends_on:
      - backend
    ports:
      - "127.0.0.1:3000:80"
```

`backend`'s in-Docker `DATABASE_URL` points at service name `db:5432`, set directly in `environment:` rather than `.env` — the host-side `.env` (`localhost:5435`) used for local non-Docker dev (`uv run uvicorn ...`) is untouched. `test-db` stays dev-only, used by `pytest`, not part of the "run the app" path.

**One command**: `docker compose up --build` starts `db` + `backend` + `frontend`; open `http://localhost:3000`.

## Testing approach

- **Component/unit tests**: Vitest + React Testing Library for `ArticleCard`, `ArticleFilters`, `Pagination`, and each AI component's available-vs-coming-soon branching, mocking `src/api/*` directly (no network in unit tests, mirroring the backend's domain-layer test philosophy).
- **API client tests**: mock `fetch` to verify `src/api/articles.ts` builds correct query strings/bodies, and that `src/api/ai.ts` correctly converts 404/501/network errors into `{available: false}`.
- **No E2E suite** (Cypress/Playwright) for this phase — YAGNI for a capstone project. Manual smoke test instead: run `docker compose up --build`, verify list/filter/sort/paginate/refresh/detail/ask-page against the real backend.
- **Type safety**: `src/types/article.ts` mirrors the backend's JSON response shape (including `posted_at` as an ISO string) so a backend field rename becomes a frontend compile error, not a silent runtime bug.

## Out of scope for this spec

- Implementing the AIB-512 AI backend endpoints (`/articles/{id}/summary`, `/articles/{id}/related`, `/chat/ask`) — frontend only, stub-aware.
- E2E browser test automation.
- User accounts/auth, multi-user concerns — unchanged from Phase 1.
- SSR/Next.js — a client-rendered SPA is sufficient; no SEO/SSR requirement for a personal capstone demo.
- Persisting Ask-AI chat history across page reloads.
