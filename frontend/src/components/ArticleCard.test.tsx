import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
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

function StateProbe() {
  const location = useLocation();
  const state = location.state as { listSearch?: string } | null;
  return <div data-testid="carried">{state?.listSearch ?? "none"}</div>;
}

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

  it("carries the current list filters forward when opening an article", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(
      <MemoryRouter initialEntries={["/?sort=posted_at_desc"]}>
        <Routes>
          <Route path="/" element={<ArticleCard article={baseArticle} />} />
          <Route path="/articles/:id" element={<StateProbe />} />
        </Routes>
      </MemoryRouter>
    );

    await userEvent.click(screen.getByText("Test Article"));

    expect(screen.getByTestId("carried")).toHaveTextContent("?sort=posted_at_desc");
  });
});
