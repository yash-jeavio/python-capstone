import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../testUtils";
import { RelatedArticles } from "./RelatedArticles";
import type { Article } from "../types/article";
import * as ai from "../api/ai";

vi.mock("../api/ai");

beforeEach(() => {
  vi.resetAllMocks();
});

function article(id: number, title: string): Article {
  return {
    id,
    title,
    url: "https://example.com",
    author: "jdoe",
    score: 10,
    comment_count: 1,
    item_type: "story",
    sources: ["top"],
    posted_at: "2026-01-01T00:00:00Z",
  };
}

describe("RelatedArticles", () => {
  it("renders the related article titles as links", async () => {
    vi.mocked(ai.getRelated).mockResolvedValue({
      state: "ok",
      data: { related: [article(2, "Related One"), article(3, "Related Two")] },
    });
    render(renderWithProviders(<RelatedArticles articleId={1} />));

    await waitFor(() => expect(screen.getByRole("link", { name: "Related One" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Related Two" })).toBeInTheDocument();
  });

  it("reports when AI is not configured", async () => {
    vi.mocked(ai.getRelated).mockResolvedValue({ state: "unconfigured" });
    render(renderWithProviders(<RelatedArticles articleId={1} />));
    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
  });

  it("offers a retry when the lookup failed", async () => {
    vi.mocked(ai.getRelated).mockResolvedValue({ state: "failed" });
    render(renderWithProviders(<RelatedArticles articleId={1} />));

    await waitFor(() => expect(screen.getByText(/couldn't load/i)).toBeInTheDocument());

    vi.mocked(ai.getRelated).mockResolvedValue({
      state: "ok",
      data: { related: [article(2, "Related One")] },
    });
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByRole("link", { name: "Related One" })).toBeInTheDocument());
  });

  it("shows an empty-state message rather than a retry when nothing is related", async () => {
    vi.mocked(ai.getRelated).mockResolvedValue({ state: "ok", data: { related: [] } });
    render(renderWithProviders(<RelatedArticles articleId={1} />));

    await waitFor(() => expect(screen.getByText(/no related articles/i)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
