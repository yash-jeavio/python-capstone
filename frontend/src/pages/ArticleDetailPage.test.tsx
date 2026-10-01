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
