# React UI & Docker Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React (Vite + TypeScript + Tailwind) frontend covering all current Phase 1 API features, with stub-aware UI for the planned AIB-512 AI features, and unify backend + frontend + database into one `docker-compose.yml` so the whole stack starts with `docker compose up --build`.

**Architecture:** A client-rendered SPA in `frontend/` talks to the existing FastAPI backend over relative `/api/*` paths — proxied to `localhost:8000` by Vite in dev, and to the `backend` container by Nginx in Docker. An isolated `src/api/` layer is the only code that touches `fetch`; AI-feature calls (`summary`, `related`, `ask`) are wrapped so a 404/501/network error (the endpoint doesn't exist on the backend yet) resolves to `{available: false}` instead of throwing, and components render a `ComingSoonBadge` in that case.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind CSS, React Router, TanStack Query, Vitest + React Testing Library. Docker: 2 Dockerfiles (backend: python+uv; frontend: node build → nginx) plus an extended `docker-compose.yml`.

**Spec:** `docs/superpowers/specs/2026-10-01-react-ui-and-docker-design.md`

## Global Constraints

- All frontend API calls use relative `/api/...` paths — never an absolute `http://localhost:8000` URL — so the same code works against Vite's dev proxy and Nginx's prod proxy.
- The three AI endpoints (`GET /articles/{id}/summary`, `GET /articles/{id}/related`, `POST /chat/ask`) must treat a `404`/`501`/network error as "not available" (render `ComingSoonBadge`), and must NOT treat any other status (e.g. `500`) that way — those still throw and surface as a real error.
- No E2E test suite (Cypress/Playwright) this phase — component/unit tests plus one manual full-stack smoke test only.
- `test-db` (existing compose service) stays dev-only for `pytest` — it is not part of the "run the app" path and is not touched by this plan.
- The backend's in-Docker `DATABASE_URL` and `TEST_DATABASE_URL` are set via `docker-compose.yml`'s `environment:` block, not `.env` — local non-Docker dev (`uv run uvicorn ...` against `localhost:5435`) must keep working unmodified. Both vars are required because `app/database/session.py` builds its engine from `get_settings()` at import time, and the `Settings` model requires both fields even though only `database_url` is ever actually used by the running app.
- Frontend language is TypeScript throughout; styling is Tailwind CSS utility classes, no separate hand-written stylesheets beyond the Tailwind entrypoint.

## Review Focus

- Empty result set: a filter combination that matches zero articles must render an explicit empty state, not a blank area or a `.map` crash on `[]`.
- Pagination's last-page boundary: since `GET /articles` returns a bare array with no total count, a page that happens to return exactly `page_size` items looks identical to a page with more after it — "Next" will be enabled even on a true last page. This is a documented limitation, not a bug to hide; it must be covered by a test that pins the current (imperfect) behavior so a future fix is a deliberate change, not an accidental regression.
- Articles with `url: null` (Ask HN posts) must not render a broken or empty outbound link.
- Clicking "Refresh" twice before the first request resolves must not fire two requests — the button must be disabled while a refresh is in flight.
- Keyword search containing characters like `&`, `%`, `+`, or spaces must be correctly URL-encoded in the query string sent to the backend.

---

## Task 1: Scaffold the frontend project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx` (placeholder, replaced fully in Task 11)
- Create: `frontend/src/index.css`
- Create: `frontend/src/setupTests.ts`
- Create: `frontend/.gitignore`

**Interfaces:**
- Produces: a working Vite+React+TS+Tailwind+Vitest project under `frontend/` that builds and runs `npm test`. No app logic yet — later tasks fill in `src/api`, `src/components`, `src/pages`, and replace the placeholder `App.tsx`.

This task has no business logic, so it's verified by the build succeeding rather than a unit test.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "hn-capstone-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "@tanstack/react-query": "^5.59.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^14.3.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "jsdom": "^24.1.3",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.10",
    "typescript": "^5.5.4",
    "vite": "^5.4.2",
    "vitest": "^1.6.0"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 5: Create `frontend/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hacker News AI Insights</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 8: Create `frontend/src/setupTests.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 9: Create a placeholder `frontend/src/App.tsx`**

```tsx
export function App() {
  return <div>Hacker News AI Insights</div>;
}
```

- [ ] **Step 10: Create `frontend/src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 11: Create `frontend/.gitignore`**

```
node_modules
dist
```

- [ ] **Step 12: Install dependencies**

Run: `cd frontend && npm install`
Expected: installs cleanly with no errors.

- [ ] **Step 13: Verify the scaffold builds**

Run: `cd frontend && npm run build`
Expected: completes successfully, producing `frontend/dist/`.

- [ ] **Step 14: Commit**

```bash
git add frontend
git commit -m "chore: scaffold Vite + React + TypeScript + Tailwind frontend"
```

---

## Task 2: API client core & shared types

**Files:**
- Create: `frontend/src/types/article.ts`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `Article`, `SourceFilter`, `SortOption`, `ArticleFilters`, `RefreshResult` types; `apiFetch<T>(path: string, init?: RequestInit): Promise<T>`; `class ApiError extends Error { status: number }`.

- [ ] **Step 1: Create `frontend/src/types/article.ts`**

```ts
export interface Article {
  id: number;
  title: string;
  url: string | null;
  author: string | null;
  score: number;
  comment_count: number;
  item_type: string;
  sources: string[];
  posted_at: string;
}

export type SourceFilter = "top" | "best" | "ask" | "show";
export type SortOption = "score_desc" | "posted_at_desc";

export interface ArticleFilters {
  keyword?: string;
  min_score?: number;
  source?: SourceFilter;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface RefreshResult {
  fetched: number;
  created: number;
  updated: number;
  failed: number;
}
```

- [ ] **Step 2: Write the failing test for `apiFetch`**

Create `frontend/src/api/client.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { apiFetch, ApiError } from "./client";

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ hello: "world" }),
      })
    );

    const result = await apiFetch<{ hello: string }>("/test");
    expect(result).toEqual({ hello: "world" });
  });

  it("calls fetch with the /api prefix", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/articles");
    expect(fetchMock).toHaveBeenCalledWith("/api/articles", expect.anything());
  });

  it("throws an ApiError carrying the status on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    const error = await apiFetch("/missing").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- src/api/client.test.ts`
Expected: FAIL — `./client` has no exported member `apiFetch`/`ApiError`.

- [ ] **Step 4: Implement `frontend/src/api/client.ts`**

```ts
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `Request to ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- src/api/client.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/article.ts frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): add typed API client core and shared article types"
```

---

## Task 3: Articles API module

**Files:**
- Create: `frontend/src/api/articles.ts`
- Test: `frontend/src/api/articles.test.ts`

**Interfaces:**
- Consumes: `apiFetch` from `./client` (Task 2); `Article`, `ArticleFilters`, `RefreshResult` from `../types/article` (Task 2).
- Produces: `listArticles(filters?: ArticleFilters): Promise<Article[]>`, `getArticle(id: number): Promise<Article>`, `refreshArticles(): Promise<RefreshResult>`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/api/articles.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { listArticles, getArticle, refreshArticles } from "./articles";

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) }));
}

describe("articles api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds a query string from the provided filters plus pagination defaults", async () => {
    mockFetchOnce([]);
    await listArticles({ keyword: "ai" });
    expect(fetch).toHaveBeenCalledWith("/api/articles?keyword=ai&page=1&page_size=20", expect.anything());
  });

  it("defaults to page 1 / page_size 20 with no filters", async () => {
    mockFetchOnce([]);
    await listArticles({});
    expect(fetch).toHaveBeenCalledWith("/api/articles?page=1&page_size=20", expect.anything());
  });

  it("URL-encodes special characters in the keyword", async () => {
    mockFetchOnce([]);
    await listArticles({ keyword: "rust & go" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/articles?keyword=rust+%26+go&page=1&page_size=20",
      expect.anything()
    );
  });

  it("fetches a single article by id", async () => {
    mockFetchOnce({ id: 1 });
    await getArticle(1);
    expect(fetch).toHaveBeenCalledWith("/api/articles/1", expect.anything());
  });

  it("posts to the refresh endpoint", async () => {
    mockFetchOnce({ fetched: 1, created: 1, updated: 0, failed: 0 });
    await refreshArticles();
    expect(fetch).toHaveBeenCalledWith("/api/articles/refresh", expect.objectContaining({ method: "POST" }));
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- src/api/articles.test.ts`
Expected: FAIL — module `./articles` does not exist.

- [ ] **Step 3: Implement `frontend/src/api/articles.ts`**

```ts
import { apiFetch } from "./client";
import type { Article, ArticleFilters, RefreshResult } from "../types/article";

function buildQuery(filters: ArticleFilters): string {
  const params = new URLSearchParams();
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));
  if (filters.source) params.set("source", filters.source);
  if (filters.sort) params.set("sort", filters.sort);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.page_size ?? 20));
  return params.toString();
}

export function listArticles(filters: ArticleFilters = {}): Promise<Article[]> {
  return apiFetch<Article[]>(`/articles?${buildQuery(filters)}`);
}

export function getArticle(id: number): Promise<Article> {
  return apiFetch<Article>(`/articles/${id}`);
}

export function refreshArticles(): Promise<RefreshResult> {
  return apiFetch<RefreshResult>(`/articles/refresh`, { method: "POST" });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- src/api/articles.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/articles.ts frontend/src/api/articles.test.ts
git commit -m "feat(frontend): add articles API module (list/get/refresh)"
```

---

## Task 4: AI API module (stub-aware)

**Files:**
- Create: `frontend/src/api/ai.ts`
- Test: `frontend/src/api/ai.test.ts`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError` from `./client` (Task 2); `Article` from `../types/article` (Task 2).
- Produces: `type AiResult<T> = { available: true; data: T } | { available: false }`; `getSummary(articleId: number): Promise<AiResult<{summary: string}>>`; `getRelated(articleId: number): Promise<AiResult<{related: Article[]}>>`; `askQuestion(question: string): Promise<AiResult<{answer: string; sources: Article[]}>>`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/api/ai.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { getSummary, getRelated, askQuestion } from "./ai";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ai api stub handling", () => {
  it("returns available data when the backend has the endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ summary: "short summary" }) })
    );

    const result = await getSummary(1);
    expect(result).toEqual({ available: true, data: { summary: "short summary" } });
  });

  it("treats a 404 as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    const result = await getSummary(1);
    expect(result).toEqual({ available: false });
  });

  it("treats a 501 as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 501 }));

    const result = await getRelated(1);
    expect(result).toEqual({ available: false });
  });

  it("treats a network error as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const result = await askQuestion("what is trending?");
    expect(result).toEqual({ available: false });
  });

  it("rethrows unexpected server errors instead of hiding them", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    await expect(getSummary(1)).rejects.toThrow();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- src/api/ai.test.ts`
Expected: FAIL — module `./ai` does not exist.

- [ ] **Step 3: Implement `frontend/src/api/ai.ts`**

```ts
import { apiFetch, ApiError } from "./client";
import type { Article } from "../types/article";

export type AiResult<T> = { available: true; data: T } | { available: false };

async function callStub<T>(path: string, init?: RequestInit): Promise<AiResult<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { available: true, data };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
      return { available: false };
    }
    if (err instanceof TypeError) {
      return { available: false };
    }
    throw err;
  }
}

export function getSummary(articleId: number): Promise<AiResult<{ summary: string }>> {
  return callStub(`/articles/${articleId}/summary`);
}

export function getRelated(articleId: number): Promise<AiResult<{ related: Article[] }>> {
  return callStub(`/articles/${articleId}/related`);
}

export function askQuestion(question: string): Promise<AiResult<{ answer: string; sources: Article[] }>> {
  return callStub(`/chat/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- src/api/ai.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/ai.ts frontend/src/api/ai.test.ts
git commit -m "feat(frontend): add stub-aware AI API module"
```

---

## Task 5: AI display components

**Files:**
- Create: `frontend/src/components/ComingSoonBadge.tsx`
- Create: `frontend/src/components/AiSummaryPanel.tsx`
- Create: `frontend/src/components/RelatedArticles.tsx`
- Create: `frontend/src/testUtils.tsx`
- Test: `frontend/src/components/ComingSoonBadge.test.tsx`
- Test: `frontend/src/components/AiSummaryPanel.test.tsx`
- Test: `frontend/src/components/RelatedArticles.test.tsx`

**Interfaces:**
- Consumes: `getSummary`, `getRelated` from `../api/ai` (Task 4); `Article` type (Task 2).
- Produces: `ComingSoonBadge({label}: {label: string})`; `AiSummaryPanel({articleId, variant}: {articleId: number; variant?: "compact" | "full"})`; `RelatedArticles({articleId}: {articleId: number})`; `renderWithProviders(children: ReactNode)` test helper wrapping `QueryClientProvider` + `MemoryRouter`, reused by every later component test that needs React Query and/or routing context.

- [ ] **Step 1: Create the shared test helper `frontend/src/testUtils.tsx`**

```tsx
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

export function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Write the failing test for `ComingSoonBadge`**

Create `frontend/src/components/ComingSoonBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ComingSoonBadge } from "./ComingSoonBadge";

describe("ComingSoonBadge", () => {
  it("renders the label with a coming-in-Phase-2 suffix", () => {
    render(<ComingSoonBadge label="AI summary" />);
    expect(screen.getByText("AI summary — coming in Phase 2")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/ComingSoonBadge.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement `frontend/src/components/ComingSoonBadge.tsx`**

```tsx
export function ComingSoonBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
      {label} — coming in Phase 2
    </span>
  );
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/ComingSoonBadge.test.tsx`
Expected: PASS.

- [ ] **Step 6: Write the failing tests for `AiSummaryPanel`**

Create `frontend/src/components/AiSummaryPanel.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { AiSummaryPanel } from "./AiSummaryPanel";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AiSummaryPanel", () => {
  it("renders the summary when the backend has it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ summary: "a short summary" }) })
    );
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText("a short summary")).toBeInTheDocument());
  });

  it("renders a coming-soon badge when the endpoint doesn't exist yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/AiSummaryPanel.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 8: Implement `frontend/src/components/AiSummaryPanel.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { getSummary } from "../api/ai";
import { ComingSoonBadge } from "./ComingSoonBadge";

export function AiSummaryPanel({
  articleId,
  variant = "full",
}: {
  articleId: number;
  variant?: "compact" | "full";
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["summary", articleId],
    queryFn: () => getSummary(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading summary...</p>;
  }
  if (!data?.available) {
    return <ComingSoonBadge label="AI summary" />;
  }
  return (
    <p className={variant === "compact" ? "line-clamp-2 text-sm text-gray-600" : "text-base text-gray-700"}>
      {data.data.summary}
    </p>
  );
}
```

- [ ] **Step 9: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/AiSummaryPanel.test.tsx`
Expected: PASS.

- [ ] **Step 10: Write the failing tests for `RelatedArticles`**

Create `frontend/src/components/RelatedArticles.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { RelatedArticles } from "./RelatedArticles";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RelatedArticles", () => {
  it("renders related article titles when available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ related: [{ id: 2, title: "Related One" }] }),
      })
    );
    render(renderWithProviders(<RelatedArticles articleId={1} />));
    await waitFor(() => expect(screen.getByText("Related One")).toBeInTheDocument());
  });

  it("renders a coming-soon badge when not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<RelatedArticles articleId={1} />));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/RelatedArticles.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 12: Implement `frontend/src/components/RelatedArticles.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getRelated } from "../api/ai";
import { ComingSoonBadge } from "./ComingSoonBadge";

export function RelatedArticles({ articleId }: { articleId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["related", articleId],
    queryFn: () => getRelated(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading related articles...</p>;
  }
  if (!data?.available) {
    return <ComingSoonBadge label="Related articles" />;
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

- [ ] **Step 13: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/RelatedArticles.test.tsx`
Expected: PASS.

- [ ] **Step 14: Commit**

```bash
git add frontend/src/testUtils.tsx frontend/src/components/ComingSoonBadge.tsx frontend/src/components/ComingSoonBadge.test.tsx frontend/src/components/AiSummaryPanel.tsx frontend/src/components/AiSummaryPanel.test.tsx frontend/src/components/RelatedArticles.tsx frontend/src/components/RelatedArticles.test.tsx
git commit -m "feat(frontend): add AI summary/related components with coming-soon fallback"
```

---

## Task 6: Core article display components

**Files:**
- Create: `frontend/src/components/ArticleCard.tsx`
- Create: `frontend/src/components/Pagination.tsx`
- Test: `frontend/src/components/ArticleCard.test.tsx`
- Test: `frontend/src/components/Pagination.test.tsx`

**Interfaces:**
- Consumes: `Article` type (Task 2); `AiSummaryPanel` (Task 5); `renderWithProviders` (Task 5).
- Produces: `ArticleCard({article}: {article: Article})`; `Pagination({page, hasNextPage, onPageChange}: {page: number; hasNextPage: boolean; onPageChange: (page: number) => void})`.

- [ ] **Step 1: Write the failing tests for `ArticleCard`**

Create `frontend/src/components/ArticleCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { ArticleCard } from "./ArticleCard";
import { renderWithProviders } from "../testUtils";
import type { Article } from "../types/article";

afterEach(() => {
  vi.unstubAllGlobals();
});

const baseArticle: Article = {
  id: 1,
  title: "Test Article",
  url: "https://example.com",
  author: "jdoe",
  score: 42,
  comment_count: 3,
  item_type: "story",
  sources: ["top", "best"],
  posted_at: "2026-01-01T00:00:00Z",
};

describe("ArticleCard", () => {
  it("renders article title, score, and sources", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<ArticleCard article={baseArticle} />));
    expect(screen.getByText("Test Article")).toBeInTheDocument();
    expect(screen.getByText(/42 points/)).toBeInTheDocument();
    expect(screen.getByText("top")).toBeInTheDocument();
    expect(screen.getByText("best")).toBeInTheDocument();
  });

  it("links to the original HN url when present", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<ArticleCard article={baseArticle} />));
    expect(screen.getByText("View original ↗")).toHaveAttribute("href", "https://example.com");
  });

  it("renders no outbound link for a null url (Ask HN post)", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<ArticleCard article={{ ...baseArticle, url: null }} />));
    expect(screen.queryByText("View original ↗")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/ArticleCard.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `frontend/src/components/ArticleCard.tsx`**

```tsx
import { Link } from "react-router-dom";
import type { Article } from "../types/article";
import { AiSummaryPanel } from "./AiSummaryPanel";

export function ArticleCard({ article }: { article: Article }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <Link to={`/articles/${article.id}`} className="text-lg font-semibold text-gray-900 hover:underline">
        {article.title}
      </Link>
      <div className="mt-1 text-sm text-gray-500">
        {article.author ?? "unknown"} · {article.score} points · {article.comment_count} comments
      </div>
      <div className="mt-1 flex gap-1">
        {article.sources.map((source) => (
          <span key={source} className="rounded bg-orange-100 px-2 py-0.5 text-xs text-orange-700">
            {source}
          </span>
        ))}
      </div>
      {article.url && (
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block text-sm text-blue-600 hover:underline"
        >
          View original ↗
        </a>
      )}
      <div className="mt-2">
        <AiSummaryPanel articleId={article.id} variant="compact" />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/ArticleCard.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing tests for `Pagination`**

Create `frontend/src/components/Pagination.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("disables Prev on page 1", () => {
    render(<Pagination page={1} hasNextPage={true} onPageChange={vi.fn()} />);
    expect(screen.getByText("Prev")).toBeDisabled();
  });

  it("disables Next when hasNextPage is false", () => {
    render(<Pagination page={2} hasNextPage={false} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).toBeDisabled();
  });

  it("enables Next when a full page was returned, even on what may be the last page", () => {
    // Known limitation (documented in the plan's Review Focus): the backend
    // returns no total count, so "a full page came back" is the only signal
    // we have, and it can't distinguish a true last page from one that isn't.
    render(<Pagination page={5} hasNextPage={true} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).not.toBeDisabled();
  });

  it("calls onPageChange with the next page number", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} hasNextPage={true} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("Next"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("calls onPageChange with the previous page number", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} hasNextPage={true} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("Prev"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/Pagination.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 7: Implement `frontend/src/components/Pagination.tsx`**

```tsx
export function Pagination({
  page,
  hasNextPage,
  onPageChange,
}: {
  page: number;
  hasNextPage: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-center gap-4">
      <button
        className="rounded border border-gray-300 px-3 py-1 disabled:opacity-50"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Prev
      </button>
      <span className="text-sm text-gray-600">Page {page}</span>
      <button
        className="rounded border border-gray-300 px-3 py-1 disabled:opacity-50"
        disabled={!hasNextPage}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/Pagination.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ArticleCard.tsx frontend/src/components/ArticleCard.test.tsx frontend/src/components/Pagination.tsx frontend/src/components/Pagination.test.tsx
git commit -m "feat(frontend): add ArticleCard and Pagination components"
```

---

## Task 7: Filter & refresh controls

**Files:**
- Create: `frontend/src/components/ArticleFilters.tsx`
- Create: `frontend/src/components/RefreshButton.tsx`
- Test: `frontend/src/components/ArticleFilters.test.tsx`
- Test: `frontend/src/components/RefreshButton.test.tsx`

**Interfaces:**
- Consumes: `ArticleFilters`, `SourceFilter`, `SortOption` types (Task 2); `refreshArticles` from `../api/articles` (Task 3); `renderWithProviders` (Task 5).
- Produces: `ArticleFilters({filters, onChange}: {filters: ArticleFiltersType; onChange: (filters: ArticleFiltersType) => void})`; `RefreshButton()`.

- [ ] **Step 1: Write the failing tests for `ArticleFilters`**

Create `frontend/src/components/ArticleFilters.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { ArticleFilters } from "./ArticleFilters";

afterEach(() => {
  vi.useRealTimers();
});

describe("ArticleFilters", () => {
  it("debounces keyword changes before calling onChange", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Search title..."), { target: { value: "rust" } });
    expect(onChange).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(onChange).toHaveBeenCalledWith({ keyword: "rust", page: 1 });
  });

  it("updates min_score immediately without debounce", () => {
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Min score"), { target: { value: "50" } });
    expect(onChange).toHaveBeenCalledWith({ min_score: 50, page: 1 });
  });

  it("updates the source filter immediately", () => {
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByDisplayValue("All sources"), { target: { value: "top" } });
    expect(onChange).toHaveBeenCalledWith({ source: "top", page: 1 });
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/ArticleFilters.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `frontend/src/components/ArticleFilters.tsx`**

```tsx
import { useEffect, useState } from "react";
import type { ArticleFilters as Filters, SourceFilter, SortOption } from "../types/article";

export function ArticleFilters({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (filters: Filters) => void;
}) {
  const [keyword, setKeyword] = useState(filters.keyword ?? "");

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (keyword !== (filters.keyword ?? "")) {
        onChange({ ...filters, keyword: keyword || undefined, page: 1 });
      }
    }, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword]);

  return (
    <div className="flex flex-wrap gap-3 rounded-lg border border-gray-200 p-4">
      <input
        type="text"
        placeholder="Search title..."
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="rounded border border-gray-300 px-2 py-1"
      />
      <input
        type="number"
        min={0}
        placeholder="Min score"
        value={filters.min_score ?? ""}
        onChange={(e) =>
          onChange({ ...filters, min_score: e.target.value ? Number(e.target.value) : undefined, page: 1 })
        }
        className="w-28 rounded border border-gray-300 px-2 py-1"
      />
      <select
        value={filters.source ?? ""}
        aria-label="Source"
        onChange={(e) =>
          onChange({ ...filters, source: (e.target.value || undefined) as SourceFilter | undefined, page: 1 })
        }
        className="rounded border border-gray-300 px-2 py-1"
      >
        <option value="">All sources</option>
        <option value="top">Top</option>
        <option value="best">Best</option>
        <option value="ask">Ask</option>
        <option value="show">Show</option>
      </select>
      <select
        value={filters.sort ?? "score_desc"}
        aria-label="Sort"
        onChange={(e) => onChange({ ...filters, sort: e.target.value as SortOption, page: 1 })}
        className="rounded border border-gray-300 px-2 py-1"
      >
        <option value="score_desc">Score (high to low)</option>
        <option value="posted_at_desc">Newest first</option>
      </select>
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/ArticleFilters.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing tests for `RefreshButton`**

Create `frontend/src/components/RefreshButton.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { RefreshButton } from "./RefreshButton";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RefreshButton", () => {
  it("shows the refresh summary after a successful refresh", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ fetched: 10, created: 8, updated: 2, failed: 0 }),
      })
    );
    render(renderWithProviders(<RefreshButton />));
    fireEvent.click(screen.getByText("Refresh from Hacker News"));
    await waitFor(() =>
      expect(screen.getByText(/Fetched 10, created 8, updated 2, failed 0/)).toBeInTheDocument()
    );
  });

  it("shows an error message when the refresh request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    render(renderWithProviders(<RefreshButton />));
    fireEvent.click(screen.getByText("Refresh from Hacker News"));
    await waitFor(() => expect(screen.getByText("Refresh failed. Please try again.")).toBeInTheDocument());
  });

  it("disables the button while a refresh is in flight so double-clicks can't fire two requests", async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveFetch = resolve;
        })
      )
    );
    render(renderWithProviders(<RefreshButton />));
    const button = screen.getByText("Refresh from Hacker News");
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText("Refreshing...")).toBeDisabled());

    resolveFetch({ ok: true, json: () => Promise.resolve({ fetched: 0, created: 0, updated: 0, failed: 0 }) });
    await waitFor(() => expect(screen.getByText("Refresh from Hacker News")).not.toBeDisabled());
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && npm test -- src/components/RefreshButton.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 7: Implement `frontend/src/components/RefreshButton.tsx`**

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { refreshArticles } from "../api/articles";
import type { RefreshResult } from "../types/article";

export function RefreshButton() {
  const queryClient = useQueryClient();
  const [lastResult, setLastResult] = useState<RefreshResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: refreshArticles,
    onSuccess: (result) => {
      setLastResult(result);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: () => {
      setError("Refresh failed. Please try again.");
    },
  });

  return (
    <div className="flex items-center gap-3">
      <button
        className="rounded bg-orange-600 px-4 py-2 text-white disabled:opacity-50"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? "Refreshing..." : "Refresh from Hacker News"}
      </button>
      {lastResult && (
        <span className="text-sm text-gray-600">
          Fetched {lastResult.fetched}, created {lastResult.created}, updated {lastResult.updated}, failed{" "}
          {lastResult.failed}
        </span>
      )}
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && npm test -- src/components/RefreshButton.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ArticleFilters.tsx frontend/src/components/ArticleFilters.test.tsx frontend/src/components/RefreshButton.tsx frontend/src/components/RefreshButton.test.tsx
git commit -m "feat(frontend): add ArticleFilters and RefreshButton components"
```

---

## Task 8: Articles list page

**Files:**
- Create: `frontend/src/pages/ArticlesListPage.tsx`
- Test: `frontend/src/pages/ArticlesListPage.test.tsx`

**Interfaces:**
- Consumes: `listArticles` (Task 3); `ArticleFilters` type (Task 2); `ArticleFilters`, `ArticleCard`, `Pagination`, `RefreshButton` components (Tasks 6, 7); `renderWithProviders` (Task 5).
- Produces: `ArticlesListPage()`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/ArticlesListPage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { ArticlesListPage } from "./ArticlesListPage";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

const sampleArticle = {
  id: 1,
  title: "Sample Article",
  url: "https://example.com",
  author: "jdoe",
  score: 10,
  comment_count: 1,
  item_type: "story",
  sources: ["top"],
  posted_at: "2026-01-01T00:00:00Z",
};

function mockListAndAiCalls(articles: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/articles?")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(articles) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    })
  );
}

describe("ArticlesListPage", () => {
  it("renders articles returned by the API", async () => {
    mockListAndAiCalls([sampleArticle]);
    render(renderWithProviders(<ArticlesListPage />));
    await waitFor(() => expect(screen.getByText("Sample Article")).toBeInTheDocument());
  });

  it("renders an empty state when no articles match the filters", async () => {
    mockListAndAiCalls([]);
    render(renderWithProviders(<ArticlesListPage />));
    await waitFor(() => expect(screen.getByText("No articles match your filters.")).toBeInTheDocument());
  });

  it("shows a retry button when the list request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    render(renderWithProviders(<ArticlesListPage />));
    await waitFor(() => expect(screen.getByText("Failed to load articles.")).toBeInTheDocument());
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/pages/ArticlesListPage.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `frontend/src/pages/ArticlesListPage.tsx`**

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listArticles } from "../api/articles";
import type { ArticleFilters as Filters } from "../types/article";
import { ArticleFilters } from "../components/ArticleFilters";
import { ArticleCard } from "../components/ArticleCard";
import { Pagination } from "../components/Pagination";
import { RefreshButton } from "../components/RefreshButton";

const PAGE_SIZE = 20;

export function ArticlesListPage() {
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: PAGE_SIZE, sort: "score_desc" });

  const {
    data: articles,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["articles", filters],
    queryFn: () => listArticles(filters),
  });

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Hacker News Articles</h1>
        <RefreshButton />
      </div>
      <ArticleFilters filters={filters} onChange={setFilters} />
      {isLoading && <p className="mt-4 text-gray-500">Loading articles...</p>}
      {isError && (
        <div className="mt-4 flex items-center gap-3">
          <p className="text-red-600">Failed to load articles.</p>
          <button className="rounded border border-gray-300 px-3 py-1" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}
      {articles && articles.length === 0 && (
        <p className="mt-4 text-gray-500">No articles match your filters.</p>
      )}
      {articles && articles.length > 0 && (
        <>
          <div className="mt-4 space-y-3">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
          <Pagination
            page={filters.page ?? 1}
            hasNextPage={articles.length === (filters.page_size ?? PAGE_SIZE)}
            onPageChange={(page) => setFilters({ ...filters, page })}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/pages/ArticlesListPage.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ArticlesListPage.tsx frontend/src/pages/ArticlesListPage.test.tsx
git commit -m "feat(frontend): add ArticlesListPage with filters, pagination, and refresh"
```

---

## Task 9: Article detail page

**Files:**
- Create: `frontend/src/pages/ArticleDetailPage.tsx`
- Test: `frontend/src/pages/ArticleDetailPage.test.tsx`

**Interfaces:**
- Consumes: `getArticle` (Task 3); `ApiError` (Task 2); `AiSummaryPanel`, `RelatedArticles` (Task 5).
- Produces: `ArticleDetailPage()` (reads `id` from the route via `useParams`).

**Note:** this page needs `useParams`, which requires a `<Route path="/articles/:id">` context — `renderWithProviders` (a plain `MemoryRouter` with no routes) is NOT enough here. Use a dedicated render helper with `Routes`/`Route`, shown in Step 1.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/ArticleDetailPage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArticleDetailPage } from "./ArticleDetailPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderDetailPage(id: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/articles/${id}`]}>
        <Routes>
          <Route path="/articles/:id" element={<ArticleDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const sampleArticle = {
  id: 1,
  title: "Detail Article",
  url: "https://example.com",
  author: "jdoe",
  score: 10,
  comment_count: 1,
  item_type: "story",
  sources: ["top"],
  posted_at: "2026-01-01T00:00:00Z",
};

describe("ArticleDetailPage", () => {
  it("renders article details when found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url === "/api/articles/1") {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(sampleArticle) });
        }
        return Promise.resolve({ ok: false, status: 404 });
      })
    );
    renderDetailPage("1");
    await waitFor(() => expect(screen.getByText("Detail Article")).toBeInTheDocument());
  });

  it("renders a not-found state for a missing article", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    renderDetailPage("999");
    await waitFor(() => expect(screen.getByText("Article not found.")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/pages/ArticleDetailPage.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `frontend/src/pages/ArticleDetailPage.tsx`**

```tsx
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getArticle } from "../api/articles";
import { ApiError } from "../api/client";
import { AiSummaryPanel } from "../components/AiSummaryPanel";
import { RelatedArticles } from "../components/RelatedArticles";

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const articleId = Number(id);

  const {
    data: article,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["article", articleId],
    queryFn: () => getArticle(articleId),
  });

  if (isLoading) {
    return <p className="p-6 text-gray-500">Loading article...</p>;
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="p-6">
        <p className="text-red-600">Article not found.</p>
        <Link to="/" className="text-blue-600 hover:underline">
          Back to list
        </Link>
      </div>
    );
  }

  if (!article) {
    return <p className="p-6 text-red-600">Failed to load article.</p>;
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        ← Back to list
      </Link>
      <h1 className="mt-2 text-2xl font-bold">{article.title}</h1>
      <div className="mt-1 text-sm text-gray-500">
        {article.author ?? "unknown"} · {article.score} points · {article.comment_count} comments ·{" "}
        {article.item_type}
      </div>
      {article.url && (
        <a href={article.url} target="_blank" rel="noreferrer" className="mt-1 block text-blue-600 hover:underline">
          View original ↗
        </a>
      )}
      <section className="mt-6">
        <h2 className="text-lg font-semibold">AI Summary</h2>
        <AiSummaryPanel articleId={article.id} variant="full" />
      </section>
      <section className="mt-6">
        <h2 className="text-lg font-semibold">Related Articles</h2>
        <RelatedArticles articleId={article.id} />
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/pages/ArticleDetailPage.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ArticleDetailPage.tsx frontend/src/pages/ArticleDetailPage.test.tsx
git commit -m "feat(frontend): add ArticleDetailPage with AI summary and related articles"
```

---

## Task 10: Ask AI page

**Files:**
- Create: `frontend/src/pages/AskAiPage.tsx`
- Test: `frontend/src/pages/AskAiPage.test.tsx`

**Interfaces:**
- Consumes: `askQuestion` from `../api/ai` (Task 4).
- Produces: `AskAiPage()`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/AskAiPage.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { AskAiPage } from "./AskAiPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AskAiPage", () => {
  it("shows the answer when the backend supports it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ answer: "Rust is trending.", sources: [] }),
      })
    );
    render(<AskAiPage />);
    fireEvent.change(screen.getByPlaceholderText("Ask a question..."), {
      target: { value: "What is trending?" },
    });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText("Rust is trending.")).toBeInTheDocument());
  });

  it("shows a coming-soon badge when the backend doesn't support it yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(<AskAiPage />);
    fireEvent.change(screen.getByPlaceholderText("Ask a question..."), {
      target: { value: "What is trending?" },
    });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/pages/AskAiPage.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `frontend/src/pages/AskAiPage.tsx`**

```tsx
import { useState } from "react";
import { askQuestion } from "../api/ai";

interface ChatTurn {
  question: string;
  answer: string | null;
  available: boolean;
}

export function AskAiPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed) return;
    setIsAsking(true);
    setQuestion("");
    const result = await askQuestion(trimmed);
    setTurns((prev) => [
      ...prev,
      { question: trimmed, answer: result.available ? result.data.answer : null, available: result.available },
    ]);
    setIsAsking(false);
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-bold">Ask AI</h1>
      <p className="mt-1 text-sm text-gray-500">Ask a question about the stored articles.</p>
      <div className="mt-4 space-y-4">
        {turns.map((turn, index) => (
          <div key={index} className="rounded-lg border border-gray-200 p-3">
            <p className="font-medium">{turn.question}</p>
            {turn.available ? (
              <p className="mt-1 text-gray-700">{turn.answer}</p>
            ) : (
              <span className="mt-1 inline-block rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
                Ask AI — coming in Phase 2
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question..."
          className="flex-1 rounded border border-gray-300 px-3 py-2"
        />
        <button
          onClick={handleSend}
          disabled={isAsking}
          className="rounded bg-orange-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {isAsking ? "Asking..." : "Send"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/pages/AskAiPage.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AskAiPage.tsx frontend/src/pages/AskAiPage.test.tsx
git commit -m "feat(frontend): add AskAiPage chat UI"
```

---

## Task 11: App shell — routing, nav, error boundary

**Files:**
- Modify: `frontend/src/App.tsx` (replace the Task 1 placeholder)
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `ArticlesListPage` (Task 8), `ArticleDetailPage` (Task 9), `AskAiPage` (Task 10).
- Produces: `App()`, wired into `main.tsx` from Task 1 (no change needed there — it already imports `{ App }` from `./App`).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { App } from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders the nav links and defaults to the articles list route", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(<App />);
    expect(screen.getByText("Articles")).toBeInTheDocument();
    expect(screen.getByText("Ask AI")).toBeInTheDocument();
    expect(await screen.findByText("Hacker News Articles")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- src/App.test.tsx`
Expected: FAIL — the placeholder `App` doesn't render a nav or route the list page.

- [ ] **Step 3: Replace `frontend/src/App.tsx`**

```tsx
import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArticlesListPage } from "./pages/ArticlesListPage";
import { ArticleDetailPage } from "./pages/ArticleDetailPage";
import { AskAiPage } from "./pages/AskAiPage";

const queryClient = new QueryClient();

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <p className="p-6 text-red-600">Something went wrong. Please reload the page.</p>;
    }
    return this.props.children;
  }
}

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <nav className="border-b border-gray-200 p-4">
            <div className="mx-auto flex max-w-4xl gap-6">
              <Link to="/" className="font-semibold text-gray-900">
                Articles
              </Link>
              <Link to="/ask" className="font-semibold text-gray-900">
                Ask AI
              </Link>
            </div>
          </nav>
          <Routes>
            <Route path="/" element={<ArticlesListPage />} />
            <Route path="/articles/:id" element={<ArticleDetailPage />} />
            <Route path="/ask" element={<AskAiPage />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npm test -- src/App.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: all test files pass.

- [ ] **Step 6: Verify the production build still succeeds**

Run: `cd frontend && npm run build`
Expected: completes successfully.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): wire up routing, nav, and top-level error boundary"
```

---

## Task 12: Backend Dockerfile

**Files:**
- Create: `Dockerfile` (repo root)

**Interfaces:**
- Produces: a `hn-backend` image that runs `uvicorn app.main:app` on port 8000. Consumed by `docker-compose.yml` in Task 14.

- [ ] **Step 1: Create the root `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build the image**

Run: `docker build -t hn-backend .`
Expected: builds successfully.

- [ ] **Step 3: Verify the app imports cleanly without a database connection**

`app/database/session.py` builds its SQLAlchemy engine at import time from `get_settings()`, which requires both `DATABASE_URL` and `TEST_DATABASE_URL` env vars to be set (even though engine creation itself is lazy and never actually connects). Pass placeholder values for this check:

Run: `docker run --rm -e DATABASE_URL=postgresql+psycopg2://placeholder/placeholder -e TEST_DATABASE_URL=postgresql+psycopg2://placeholder/placeholder-test hn-backend uv run python -c "import app.main; print('ok')"`
Expected: prints `ok` (confirms the image has correct dependencies/code; this works without a reachable DB because SQLAlchemy's `create_engine` is lazy, and `app.main` only creates tables inside the `lifespan` startup hook, not at import time).

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add backend Dockerfile"
```

---

## Task 13: Frontend Dockerfile + Nginx config

**Files:**
- Create: `frontend/nginx.conf`
- Create: `frontend/Dockerfile`

**Interfaces:**
- Produces: a `hn-frontend` image serving the built SPA on port 80, proxying `/api/` to `http://backend:8000/`. Consumed by `docker-compose.yml` in Task 14.

- [ ] **Step 1: Create `frontend/nginx.conf`**

```nginx
server {
    listen 80;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri /index.html;
    }
}
```

- [ ] **Step 2: Create `frontend/Dockerfile`**

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

- [ ] **Step 3: Build the image**

Run: `docker build -t hn-frontend ./frontend`
Expected: builds successfully.

- [ ] **Step 4: Verify the built static files are present**

Run: `docker run --rm hn-frontend ls /usr/share/nginx/html`
Expected: output includes `index.html` and an `assets` directory.

- [ ] **Step 5: Commit**

```bash
git add frontend/nginx.conf frontend/Dockerfile
git commit -m "feat: add frontend Dockerfile with Nginx + API proxy"
```

---

## Task 14: docker-compose integration + full-stack smoke test

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `hn-backend` image build context (repo root `Dockerfile`, Task 12), `hn-frontend` image build context (`frontend/Dockerfile`, Task 13), existing `db` service.
- Produces: a `docker compose up --build` command that starts `db`, `test-db`, `backend`, and `frontend` together.

- [ ] **Step 1: Extend `docker-compose.yml`**

Add these two services to the existing file (keep `db` and `test-db` exactly as they are):

```yaml
  backend:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg2://hn_user:hn_password@db:5432/hn_capstone
      TEST_DATABASE_URL: postgresql+psycopg2://hn_user:hn_password@test-db:5432/hn_capstone_test
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

The full file should now read:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: hn_user
      POSTGRES_PASSWORD: hn_password
      POSTGRES_DB: hn_capstone
    ports:
      - "127.0.0.1:5435:5432"
    volumes:
      - hn_db_data:/var/lib/postgresql/data

  test-db:
    image: postgres:16
    environment:
      POSTGRES_USER: hn_user
      POSTGRES_PASSWORD: hn_password
      POSTGRES_DB: hn_capstone_test
    ports:
      - "127.0.0.1:5434:5432"
    # no volume — disposable, wiped every time the container is recreated

  backend:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg2://hn_user:hn_password@db:5432/hn_capstone
      TEST_DATABASE_URL: postgresql+psycopg2://hn_user:hn_password@test-db:5432/hn_capstone_test
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

volumes:
  hn_db_data:
```

- [ ] **Step 2: Bring up the full stack**

Run: `docker compose up --build -d db backend frontend`
Expected: all three containers start without errors (`test-db` is intentionally excluded — it's dev/pytest-only, per this plan's Global Constraints).

- [ ] **Step 3: Verify the backend is reachable directly**

Run: `sleep 3 && curl -s http://localhost:8000/articles`
Expected: a JSON array (likely `[]` on a fresh database).

- [ ] **Step 4: Verify the frontend serves the SPA**

Run: `curl -s http://localhost:3000/ | grep -o '<div id="root">'`
Expected: outputs `<div id="root">`.

- [ ] **Step 5: Verify the Nginx `/api` proxy reaches the backend**

Run: `curl -s http://localhost:3000/api/articles`
Expected: the same JSON array as Step 3, confirming the proxy correctly strips `/api` and forwards to the `backend` container.

- [ ] **Step 6: Tear down**

Run: `docker compose down`
Expected: all containers stop cleanly.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: unify backend, frontend, and database into one docker-compose stack"
```

---

## Manual verification (after Task 14)

Run `docker compose up --build`, open `http://localhost:3000`, and confirm:
- The articles list loads, filters (keyword/min_score/source/sort) update results, and pagination's Prev/Next behave correctly.
- Clicking "Refresh from Hacker News" shows a loading state, then a summary, and the list updates.
- Clicking an article opens its detail page, including the AI Summary and Related Articles sections showing "coming in Phase 2" badges (since the backend doesn't implement those endpoints yet).
- The "Ask AI" page accepts a question and shows a "coming in Phase 2" badge.
