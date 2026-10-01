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
